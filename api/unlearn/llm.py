"""LLM provider chain, cache and receipt check.

The LLM writes words, never facts. Every reply is checked against the rows the tools returned in the same
turn: any construct or misconception name it mentions must appear in those rows. A reply that fails is
retried once, then replaced by a template built only from the rows, so the demo never fails.

Provider chain: Groq -> Gemini -> OpenRouter -> template, all through the openai SDK's OpenAI-compatible
endpoints. A provider with no key in .env is skipped; a provider that errors (network, rate limit) hands
over to the next one. Model names were checked against each provider's docs on 2026-10-17:
  Groq        https://api.groq.com/openai/v1                           llama-3.3-70b-versatile
  Gemini      https://generativelanguage.googleapis.com/v1beta/openai/  gemini-3.8-flash
  OpenRouter  https://openrouter.ai/api/v1                             google/gemma-4-31b-it:free
OpenRouter lists no free Llama 70B model now, so it uses a free Gemma model with tool support. Override any
model with GROQ_MODEL / GEMINI_MODEL / OPENROUTER_MODEL. UNLEARN_LLM=template turns the chain off (tests).

Replies are cached on disk by a hash of (provider, model, messages), so reruns cost nothing.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(os.getenv("UNLEARN_LLM_CACHE", Path(__file__).resolve().parents[2] / ".cache" / "llm"))
TIMEOUT_S = 20
MAX_TOKENS = 300


@dataclass(frozen=True)
class Provider:
    name: str
    key_env: str
    base_url: str
    model_env: str
    default_model: str

    @property
    def key(self) -> str | None:
        return os.getenv(self.key_env) or None

    @property
    def model(self) -> str:
        return os.getenv(self.model_env) or self.default_model


PROVIDERS = [
    Provider("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_MODEL", "llama-3.3-70b-versatile"),
    Provider("gemini", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/",
             "GEMINI_MODEL", "gemini-3.8-flash"),
    Provider("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "OPENROUTER_MODEL",
             "google/gemma-4-31b-it:free"),
]

MARK = re.compile(r"\[\[(.+?)\]\]")
MIN_NAME_LEN = 15  # shorter vocabulary names are too likely to match ordinary words


@dataclass
class Reply:
    text: str
    source: str                      # provider name, or "template"
    attempts: list[dict] = field(default_factory=list)  # [{provider, ok, problems}] for the receipt


# --- Receipt check ------------------------------------------------------------

def _strings(value) -> set[str]:
    if isinstance(value, str):
        return {value.strip().lower()}
    if isinstance(value, dict):
        return set().union(*map(_strings, value.values())) if value else set()
    if isinstance(value, (list, tuple, set)):
        return set().union(*map(_strings, value)) if value else set()
    return set()


def check_reply(text: str, turn_rows: list, vocabulary: list[str]) -> list[str]:
    """Names in `text` that the turn's tool rows don't back up. Empty means the reply passes.

    Two checks: every [[marked]] name must be a value in the rows, and any known construct or
    misconception name that appears unmarked must also be in the rows.
    """
    allowed = _strings(turn_rows)
    problems = [m.strip() for m in MARK.findall(text) if m.strip().lower() not in allowed]
    plain = MARK.sub(" ", text).lower()
    for name in vocabulary:
        n = name.strip().lower()
        # A short name can sit inside a longer one from the rows ("... in size" in "... in size when ...").
        if len(n) >= MIN_NAME_LEN and n in plain and not any(n in a for a in allowed):
            problems.append(name)
    return problems


def unmark(text: str) -> str:
    return MARK.sub(lambda m: m.group(1), text)


# --- Templates (built only from tool rows) ------------------------------------

def _join(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def template(kind: str, facts: dict) -> str:
    if kind == "recall":
        items = facts.get("recall") or []
        if not items:
            return "Welcome! This is our first session, so I'll start with a few questions."
        parts = [f"{r['misconception']} ({r['times']} times)" for r in items[:2]]
        return f"Welcome back. Last time you showed: {_join(parts)}. Let's check whether that has changed."
    if kind == "diagnosis":
        root = facts.get("root")
        if not root:
            return "I didn't find a broken prerequisite in these answers."
        chain = " → ".join(root.get("chain") or [])
        return (f"Your answers point back to a prerequisite: {root['name']}, {root['depth']} step(s) below the topic "
                f"(evidence {root['evidence']:.2f}). Path: {chain}.")
    if kind == "explain":
        steps = facts.get("steps") or []
        lines = [f"The gap is in {facts['root_name']}. Your answers showed: {facts['misconception']}."]
        if facts.get("skill"):
            lines.append(f"Let's try the {facts['skill']} approach:")
            lines += [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
        return "\n".join(lines)
    if kind == "proposal":
        who = _join(facts.get("students") or [])
        if facts["kind"] == "regroup":
            return (f"Proposal: group {who} together; WCC puts them in one cohort linked by shared confident "
                    f"misconceptions. This student's include: {_join(facts.get('shared') or [])}.")
        if facts["kind"] == "assign_practice":
            return f"Proposal: assign {who} practice on {facts['construct_name']}, the diagnosed root cause."
        return f"Proposal: let {who} skip ahead past {facts['construct_name']}."
    raise ValueError(f"no template for {kind!r}")


# --- Provider calls -----------------------------------------------------------

SYSTEM = (
    "You write short, warm messages for a maths tutoring app for school students. You only rephrase: every "
    "fact must come from FACTS, and you must not add any misconception, topic or skill that FACTS does not "
    "name. Copy each construct or misconception name exactly as written in FACTS and wrap it in double square "
    "brackets, like [[Find the lowest common multiple]]. At most 90 words. Plain text, no markdown headings."
)

AUDIENCE = {
    "recall": "the student, opening a new session with what we remember from last time",
    "diagnosis": "the student, explaining which earlier skill their answers point back to",
    "explain": "the student, teaching the gap using the skill's steps",
    "proposal": "the human teacher, justifying one proposal they can approve or reject",
}


def messages_for(kind: str, facts: dict, draft: str) -> list[dict]:
    user = (f"Message for {AUDIENCE[kind]}.\nFACTS (JSON):\n{json.dumps(facts, default=str, ensure_ascii=False)}\n"
            f"A plain draft built from the facts:\n{draft}\nRewrite the draft in your own words.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _cache_path(provider: Provider, messages: list[dict]) -> Path:
    key = json.dumps({"provider": provider.name, "model": provider.model, "messages": messages}, sort_keys=True)
    return CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()}.json"


def complete(provider: Provider, messages: list[dict]) -> tuple[str, bool]:
    """One chat completion, cached on disk. Returns (text, from_cache)."""
    path = _cache_path(provider, messages)
    if path.exists():
        return json.loads(path.read_text())["text"], True
    from openai import OpenAI

    client = OpenAI(api_key=provider.key, base_url=provider.base_url, timeout=TIMEOUT_S, max_retries=0)
    resp = client.chat.completions.create(model=provider.model, messages=messages, max_tokens=MAX_TOKENS,
                                          temperature=0.3)
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("empty completion")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"provider": provider.name, "model": provider.model, "text": text}))
    return text, False


def available() -> list[Provider]:
    if os.getenv("UNLEARN_LLM", "auto") == "template":
        return []
    return [p for p in PROVIDERS if p.key]


# --- Entry point --------------------------------------------------------------

def _template_reply(kind: str, facts: dict, turn_rows: list, vocabulary: list[str], attempts: list[dict]) -> Reply:
    text = template(kind, facts)
    problems = check_reply(text, turn_rows, vocabulary)
    if problems:  # a template is built from the rows, so this means a bug in the template or the facts
        raise AssertionError(f"template for {kind!r} named facts not in the rows: {problems}")
    return Reply(text, "template", attempts + [{"provider": "template", "ok": True, "problems": []}])


def write(kind: str, facts: dict, turn_rows: list, vocabulary: list[str]) -> Reply:
    """Words for one agent turn, backed by the turn's tool rows.

    For the first provider that answers: check the reply, retry once with the problems named, then use the
    template. A provider that errors is skipped for the next one. No provider -> template.
    """
    draft = template(kind, facts)
    attempts: list[dict] = []
    for provider in available():
        messages = messages_for(kind, facts, draft)
        try:
            for _ in range(2):
                text, cached = complete(provider, messages)
                problems = check_reply(text, turn_rows, vocabulary)
                attempts.append({"provider": provider.name, "model": provider.model, "ok": not problems,
                                 "problems": problems, "cached": cached})
                if not problems:
                    return Reply(unmark(text), provider.name, attempts)
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "These names are not in FACTS: " + "; ".join(problems)
                     + ". Rewrite using only names from FACTS, copied exactly, in [[double brackets]]."}]
        except Exception as e:  # network, auth, rate limit: try the next provider
            attempts.append({"provider": provider.name, "model": provider.model, "ok": False,
                             "error": f"{type(e).__name__}: {str(e)[:200]}"})
            continue
        return _template_reply(kind, facts, turn_rows, vocabulary, attempts)  # failed the check twice
    return _template_reply(kind, facts, turn_rows, vocabulary, attempts)
