"""Run the real-data eval (PREREGISTRATION.md): Task A and Task B, on the test students or a dev split.

    python -m eval.real.run --dev     # train students only: 80/20 of them (seed 1); results stay in data/external/
    python -m eval.real.run           # the pre-registered test run: eval/results/real/*.json (aggregates only)

Every parameter (M0 difficulties, BKT, M2's logistic regression, M3's beta) is fitted on the train side.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from eval.real import taskb
from eval.real.data import CACHE, ROOT, SUBTOPICS, info, load
from eval.real.graph import Graph
from eval.real.metrics import evaluate
from eval.real.models import BKT, M0, M0b, GraphFeatures, bkt_sequences, fit_bkt, question_difficulty, walk

OUT = ROOT / "eval/results/real"
BETAS = (0, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2)
NOGRAPH = [0, 1, 2]  # GraphFeatures columns without prerequisite suspicion


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def commit() -> dict:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "eval/real", "api"], capture_output=True, text=True,
                           cwd=ROOT).stdout.strip()
    return {"commit": sha, "uncommitted_changes": bool(dirty)}


def sides(dev: bool):
    a = load()
    if not dev:
        return a[~a.test].copy(), a[a.test].copy()
    tr = a[~a.test]
    users = np.sort(tr.UserId.unique())
    held = set(users[np.random.default_rng(1).permutation(len(users))[: int(round(0.2 * len(users)))]].tolist())
    return tr[~tr.UserId.isin(held)].copy(), tr[tr.UserId.isin(held)].copy()


def predictive_ll(p, y) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float((y * np.log(p) + (1 - y) * np.log(1 - p)).sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    args = ap.parse_args()
    train, test = sides(args.dev)
    log(f"{'dev' if args.dev else 'TEST'} run: train {train.UserId.nunique():,} students / {len(train):,} answers, "
        f"eval {test.UserId.nunique():,} / {len(test):,}")

    diff, base = question_difficulty(train)
    for df in (train, test):
        df["pq"] = df.QuestionId.map(diff).fillna(base).astype(float)
    p_sub = [float(train[train.subtopic == s].IsCorrect.mean()) for s in SUBTOPICS]

    log("fitting BKT")
    fits = [fit_bkt(s) for s in bkt_sequences(train)]
    params = [f["params"] for f in fits]
    bkt_info = {str(s): {"L0": round(p[0], 4), "T": round(p[1], 4), "S": round(p[2], 4), "G": round(p[3], 4),
                         "iterations": f["iterations"]} for s, p, f in zip(SUBTOPICS, params, fits)}

    preds = {"M0": walk(test, M0()), "M0b": walk(test, M0b(p_sub)), "M1": walk(test, BKT(params))}
    y_tr, y = train.IsCorrect.to_numpy().astype(float), test.IsCorrect.to_numpy().astype(float)
    m2_info, m3_info = {}, {}
    for variant, tag in (("primary", ""), ("sensitivity", " (12 edges)")):
        g = Graph(variant)
        log(f"M2 features, {variant} graph")
        f_tr, f_te = walk(train, GraphFeatures(g), width=4), walk(test, GraphFeatures(g), width=4)
        lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000).fit(f_tr, y_tr)
        preds["M2" + tag] = lr.predict_proba(f_te)[:, 1]
        m2_info[variant] = {"coef": [round(float(c), 4) for c in lr.coef_[0]], "intercept": round(float(lr.intercept_[0]), 4),
                            "features": ["logit(M0)", "evidence at X", "mastered X", "prerequisite suspicion"]}
        if variant == "primary":
            lr0 = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000).fit(f_tr[:, NOGRAPH], y_tr)
            preds["M2-nograph"] = lr0.predict_proba(f_te[:, NOGRAPH])[:, 1]
            m2_info["nograph"] = {"coef": [round(float(c), 4) for c in lr0.coef_[0]], "intercept": round(float(lr0.intercept_[0]), 4)}
        log(f"M3 beta grid, {variant} graph")
        lls = {b: predictive_ll(walk(train, BKT(params, b, g)), y_tr) for b in BETAS}
        beta = max(BETAS, key=lambda b: (lls[b], -b))
        preds["M3" + tag] = walk(test, BKT(params, beta, g))
        m3_info[variant] = {"beta": beta, "train_loglik": {str(b): round(v, 1) for b, v in lls.items()}}

    log("Task A metrics (1,000 student resamples)")
    rank = test.quiz_rank.to_numpy()
    subsets = {"all": np.ones(len(test), bool), "first 2 quizzes": rank <= 1, "later quizzes": rank >= 2}
    pairs = [("M2", "M1"), ("M2", "M2-nograph"), ("M3", "M1"), ("M0b", "M1"), ("M1", "M0"),
             ("M2 (12 edges)", "M1"), ("M2 (12 edges)", "M2-nograph"), ("M3 (12 edges)", "M1")]
    contrasts = [("M2", "M2-nograph", "first 2 quizzes", "later quizzes"),
                 ("M2 (12 edges)", "M2-nograph", "first 2 quizzes", "later quizzes")]
    task_a = evaluate(preds, y, test.UserId.to_numpy(), subsets, pairs, contrasts)
    task_a.update({"bkt": bkt_info, "m2": m2_info, "m3": m3_info})

    log("Task B")
    bkt = BKT(params)
    task_b = {f"k={k}, {v}": taskb.run(test, Graph(v), bkt, k) for v in ("primary", "sensitivity") for k in (5, 10)}

    meta = {"split": "dev (80/20 of train students, seed 1)" if args.dev else "test students (pre-registered)",
            **commit(), "data": info(), "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = CACHE / "dev" if args.dev else OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, body in (("task_a.json", task_a), ("task_b.json", task_b)):
        (out / name).write_text(json.dumps({"meta": meta, **body}, indent=2) + "\n")
    log(f"wrote {out}/task_a.json, task_b.json")
    for s in subsets:
        print(s, {m: v["auc"] for m, v in task_a[s]["models"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
