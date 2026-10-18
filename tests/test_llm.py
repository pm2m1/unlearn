"""Receipt check and provider chain, with a fake provider (no network)."""

import pytest

from unlearn import llm

VOCAB = ["Find the lowest common multiple", "Multiplies the two numbers together to find the lowest common multiple",
         "Believes a number is a multiple of its last digit"]
ROWS = [{"id": 3, "name": "Find the lowest common multiple",
         "miscs": ["Multiplies the two numbers together to find the lowest common multiple"]}]
FACTS = {"root": {"name": "Find the lowest common multiple", "depth": 2, "evidence": 1.2,
                  "chain": ["Add fractions", "Find the lowest common multiple"]}}


def test_check_passes_names_from_rows():
    text = "Your answers point to [[Find the lowest common multiple]]: you [[Multiplies the two numbers together to find the lowest common multiple]]."
    assert llm.check_reply(text, ROWS, VOCAB) == []


def test_check_rejects_fabricated_marked_name():
    assert llm.check_reply("You hold [[Believes fractions are pizzas]].", ROWS, VOCAB) == ["Believes fractions are pizzas"]


def test_check_rejects_real_name_not_in_this_turn():
    # A real misconception from the vocabulary, unmarked, that no tool returned this turn.
    text = "You also believes a number is a multiple of its last digit."
    assert llm.check_reply(text, ROWS, VOCAB) == ["Believes a number is a multiple of its last digit"]


@pytest.fixture
def fake_chain(monkeypatch, tmp_path):
    """One fake provider whose replies come from a list."""
    replies = []
    provider = llm.Provider("fake", "FAKE_KEY", "http://unused", "FAKE_MODEL", "fake-1")
    monkeypatch.setattr(llm, "available", lambda: [provider])
    monkeypatch.setattr(llm, "complete", lambda p, messages: (replies.pop(0), False))
    return replies


def test_good_reply_is_used_and_unmarked(fake_chain):
    fake_chain.append("This goes back to [[Find the lowest common multiple]].")
    reply = llm.write("diagnosis", FACTS, ROWS, VOCAB)
    assert (reply.source, reply.text) == ("fake", "This goes back to Find the lowest common multiple.")


def test_fabricated_reply_retries_once_then_template(fake_chain):
    fake_chain += ["You hold [[Believes fractions are pizzas]].", "Still [[Believes fractions are pizzas]]."]
    reply = llm.write("diagnosis", FACTS, ROWS, VOCAB)
    assert reply.source == "template"
    assert [a["ok"] for a in reply.attempts] == [False, False, True]
    assert reply.text == llm.template("diagnosis", FACTS)


def test_retry_can_recover(fake_chain):
    fake_chain += ["You hold [[Believes fractions are pizzas]].", "Your answers point back to [[Find the lowest common multiple]]."]
    assert llm.write("diagnosis", FACTS, ROWS, VOCAB).source == "fake"


def test_provider_error_falls_through(monkeypatch):
    bad = llm.Provider("bad", "X", "http://unused", "Y", "m")

    def boom(p, m):
        raise ConnectionError("down")
    monkeypatch.setattr(llm, "available", lambda: [bad])
    monkeypatch.setattr(llm, "complete", boom)
    reply = llm.write("diagnosis", FACTS, ROWS, VOCAB)
    assert reply.source == "template" and "ConnectionError" in reply.attempts[0]["error"]


def test_template_mode_skips_providers(monkeypatch):
    monkeypatch.setenv("UNLEARN_LLM", "template")
    monkeypatch.setenv("GROQ_API_KEY", "set-but-ignored")
    assert llm.available() == []


def test_daily_cap_stops_uncached_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("UNLEARN_LLM", "auto")
    monkeypatch.setenv("UNLEARN_LLM_DAILY_CAP", "2")
    monkeypatch.setattr(llm, "_SPENT", {"day": "", "n": 0})
    llm._spend()
    llm._spend()
    assert llm.daily_cap_reached() and llm.available() == []
    with pytest.raises(RuntimeError, match="cap"):
        llm._spend()
    monkeypatch.setenv("UNLEARN_LLM_DAILY_CAP", "0")  # unset or 0: no cap
    assert not llm.daily_cap_reached()


def test_cache_key_is_stable_and_model_specific(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    a, b = llm.PROVIDERS[0], llm.PROVIDERS[1]
    m = llm.messages_for("diagnosis", FACTS, "draft")
    assert llm._cache_path(a, m) == llm._cache_path(a, m) != llm._cache_path(b, m)


def test_malformed_reply_is_retried_then_templated(fake_chain):
    fake_chain += ["Warm message for teacher? Yes.\n *", "Yes."]
    reply = llm.write("diagnosis", FACTS, ROWS, VOCAB)
    assert reply.source == "template"
    assert any("words" in p or "list marker" in p for a in reply.attempts[:2] for p in a["problems"])


def test_app_chain_order(monkeypatch):
    monkeypatch.delenv("UNLEARN_LLM", raising=False)
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    assert [(p.name, p.model) for p in llm.available()] == [
        ("gemini", "gemini-3.8-flash"), ("gemini", "gemini-3.6-flash"), ("gemini", "gemini-3.5-flash-lite")]
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    assert llm.available()[0].name == "ollama"  # local recording: Ollama first, only when set


def test_daily_quota_cools_a_model_down(monkeypatch):
    import httpx
    from openai import RateLimitError
    monkeypatch.delenv("UNLEARN_LLM", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(llm, "_COOLDOWN", {})
    first = llm.available()[0]
    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))
    llm.note_failure(first, RateLimitError("GenerateRequestsPerDayPerProjectPerModel-FreeTier", response=resp, body=None))
    assert llm.available()[0].model == "gemini-3.6-flash"  # skipped for an hour, the next model leads
