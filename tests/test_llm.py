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
    fake_chain += ["You hold [[Believes fractions are pizzas]].", "It's [[Find the lowest common multiple]]."]
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


def test_cache_key_is_stable_and_model_specific(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    a, b = llm.PROVIDERS[0], llm.PROVIDERS[1]
    m = llm.messages_for("diagnosis", FACTS, "draft")
    assert llm._cache_path(a, m) == llm._cache_path(a, m) != llm._cache_path(b, m)
