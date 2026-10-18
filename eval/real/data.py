"""Load the Eedi NeurIPS 2020 answers for the real-data eval: our 7 SubTopics, a fixed split by student.

    python -m eval.real.data          # build data/external/real_cache/answers.pkl and print the descriptive counts

Everything this writes is per-answer data from a CC BY-NC-ND dataset, so it goes under data/external/ (git-ignored),
never into the repo. See eval/real/DATA.md and PREREGISTRATION.md.

Rows: one per answer, with the student's SubTopic (the question's one Level-3 SubjectId among ours; questions
tagged with none or more than one of ours are dropped), and the time keys the models must respect:
  ts      DateAnswered (minute resolution)
  block   (UserId, QuizId, ts): answers in one block are predicted together, from earlier answers only
  quiz_rank  the student's quizzes ordered by their first ts (then QuizId): 0 is their first quiz
"""

import ast
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/neurips2020/data"
CACHE = ROOT / "data/external/real_cache"
SUBTOPICS = (204, 219, 220, 226, 227, 228, 230)
MIN_ANSWERS = 10
TEST_SHARE = 0.2
SEED = 0


def _answers() -> pd.DataFrame:
    tr = pd.read_csv(RAW / "train_data/train_task_1_2.csv", usecols=["QuestionId", "UserId", "AnswerId", "IsCorrect"])
    te = pd.concat([pd.read_csv(RAW / f"test_data/test_{x}_answers_task_1.csv") for x in ("public", "private")])
    am = pd.read_csv(RAW / "metadata/answer_metadata_task_1_2.csv", usecols=["AnswerId", "DateAnswered", "QuizId"])
    am = am.dropna(subset=["AnswerId"]).astype({"AnswerId": "int64"})
    return pd.concat([tr, te], ignore_index=True).merge(am, on="AnswerId", how="inner")


def question_subtopics() -> tuple[dict[int, int], dict]:
    """QuestionId -> its one SubTopic among ours, plus counts of the questions dropped."""
    sm = pd.read_csv(RAW / "metadata/subject_metadata.csv", encoding="utf-8-sig")
    level = dict(zip(sm.SubjectId, sm.Level))
    qm = pd.read_csv(RAW / "metadata/question_metadata_task_1_2.csv")
    ours = qm.SubjectId.map(lambda s: sorted({x for x in ast.literal_eval(s) if level.get(x) == 3 and x in SUBTOPICS}))
    n = ours.map(len)
    keep = qm[n == 1]
    return dict(zip(keep.QuestionId, ours[n == 1].map(lambda l: l[0]))), {"one": int((n == 1).sum()), "several": int((n > 1).sum())}


def split(users: np.ndarray) -> set[int]:
    """The test students: a fixed 20% of the sorted UserIds, by a seeded permutation."""
    users = np.sort(users)
    perm = np.random.default_rng(SEED).permutation(len(users))
    return set(users[perm[: int(round(TEST_SHARE * len(users)))]].tolist())


def build() -> tuple[pd.DataFrame, dict]:
    q2s, qcounts = question_subtopics()
    a = _answers()
    a = a[a.QuestionId.isin(q2s)].copy()
    a["subtopic"] = a.QuestionId.map(q2s).astype("int16")
    per = a.groupby("UserId").size()
    a = a[a.UserId.isin(per[per >= MIN_ANSWERS].index)].copy()
    a["ts"] = pd.to_datetime(a.DateAnswered).astype("int64") // 60_000_000_000  # minutes
    a = a.drop(columns=["DateAnswered"])
    a["IsCorrect"] = a.IsCorrect.astype("int8")
    first = a.groupby(["UserId", "QuizId"]).ts.min().rename("quiz_ts").reset_index()
    first = first.sort_values(["UserId", "quiz_ts", "QuizId"])
    first["quiz_rank"] = first.groupby("UserId").cumcount().astype("int32")
    a = a.merge(first[["UserId", "QuizId", "quiz_rank"]], on=["UserId", "QuizId"])
    a = a.sort_values(["UserId", "ts", "QuizId", "AnswerId"]).reset_index(drop=True)
    test = split(a.UserId.unique())
    a["test"] = a.UserId.isin(test)
    info = {"questions_one_subtopic": qcounts["one"], "questions_several_subtopics_dropped": qcounts["several"],
            "students": int(a.UserId.nunique()), "answers": len(a),
            "train_students": int((~a.drop_duplicates("UserId").test).sum()),
            "test_students": int(a.drop_duplicates("UserId").test.sum()),
            "train_answers": int((~a.test).sum()), "test_answers": int(a.test.sum()),
            "answers_per_subtopic": {int(k): int(v) for k, v in a.subtopic.value_counts().sort_index().items()},
            "blocks": int(a.groupby(["UserId", "QuizId", "ts"]).ngroups),
            "median_answers_per_student": float(a.groupby("UserId").size().median()),
            "median_quizzes_per_student": float(a.groupby("UserId").QuizId.nunique().median())}
    return a, info


def load() -> pd.DataFrame:
    path = CACHE / "answers.pkl"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        a, info = build()
        with path.open("wb") as f:
            pickle.dump((a, info), f)
    with path.open("rb") as f:
        return pickle.load(f)[0]


def info() -> dict:
    load()
    with (CACHE / "answers.pkl").open("rb") as f:
        return pickle.load(f)[1]


if __name__ == "__main__":
    import json

    load()
    print(json.dumps(info(), indent=2))
