"""Teacher chat additions: student names map to ids, and recorded answers are served only while their rows hold."""

import json

from unlearn import tools as T
from unlearn.agents import teacher_chat as TC


def test_chat_tools_accept_a_students_name(fixture_class):
    chat = TC.TeacherChat(fixture_class)
    assert chat.student_id("Asha") == "sa" and chat.student_id("asha ") == "sa"
    assert chat.student_id("sa") == "sa" and chat.student_id("nobody") == "nobody"
    assert chat.run_tool("t", "recall", {"student_id": "Asha"}) == T.recall(fixture_class, "sa")["rows"]


def test_recorded_answer_is_served_only_while_its_rows_and_receipt_check_hold(fixture_class, tmp_path, monkeypatch):
    calls = [["keystones", {}]]
    rows = [T.keystones(fixture_class)["rows"]]
    names = [r["name"] for r in rows[0]]
    good = f"Teach {names[0]} first, then {names[1]}, because most of the topic builds on them."

    def record(text, fp):
        path = tmp_path / "recorded.json"
        path.write_text(json.dumps({"model": "test-model", "recorded_on": "2026-10-18", "answers": [
            {"class_id": fixture_class, "question": "Which skill should I teach first?", "tools": calls,
             "fingerprint": fp, "text": text}]}))
        monkeypatch.setenv("UNLEARN_RECORDED_CHAT", str(path))
        TC.recorded_answers.cache_clear()

    try:
        record(good, TC.fingerprint(calls, rows))
        out = TC.chat(fixture_class, "which skill should I teach FIRST")  # case and punctuation don't matter
        assert out["source"] == "recorded" and out["text"] == good and out["recorded"]["model"] == "test-model"
        assert TC.chat(fixture_class, "Which keystones matter?")["source"] == "template"  # other questions: live
        record(good, "a fingerprint from a class that has since changed")
        assert TC.chat(fixture_class, "Which skill should I teach first?")["source"] == "template"
        record("Teach Adds the numerators and adds the denominators when adding fractions first, it matters most.",
               TC.fingerprint(calls, rows))  # names a misconception the rows don't contain: fails the receipt check
        assert TC.chat(fixture_class, "Which skill should I teach first?")["source"] == "template"
    finally:
        monkeypatch.delenv("UNLEARN_RECORDED_CHAT")
        TC.recorded_answers.cache_clear()
