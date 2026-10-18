"""Task B: does the diagnosed root predict later errors on what depends on it? (PREREGISTRATION.md section 6)"""

from collections import Counter

import numpy as np

from eval.real.metrics import N_BOOT, SEED, ci
from eval.real.models import IDX, GraphState, root_cause_rows
from unlearn.agents.diagnoser import EVIDENCE_MIN, LEAD_MIN

MIN_EVALUABLE = 500


def diagnose(gs: GraphState, graph, targets: set[int]):
    """Pooled root_cause rows over the targets; the root is most evidence, then deepest, then lowest id.
    Returns (root or None, confident). The runner-up for `confident` is the best row on a different SubTopic."""
    best = {}
    for t in targets:
        for p, d, ev in root_cause_rows(gs, graph, t):
            if p not in best or d > best[p][0]:
                best[p] = (d, ev)
    rows = sorted(((p, d, ev) for p, (d, ev) in best.items()), key=lambda r: (-r[2], -r[1], r[0]))
    if not rows:
        return None, False
    runner_up = rows[1][2] if len(rows) > 1 else 0.0
    return rows[0][0], rows[0][2] >= EVIDENCE_MIN and rows[0][2] - runner_up >= LEAD_MIN


def split_window(rows, k: int):
    """rows: one student's answers sorted by (ts, AnswerId), with quiz_rank. First quizzes until >= k answers."""
    counts = Counter(rows["quiz_rank"])
    total, last_rank = 0, None
    for r in sorted(counts):
        total += counts[r]
        last_rank = r
        if total >= k:
            break
    win = rows["quiz_rank"] <= last_rank
    last_ts = rows["ts"][win].max()
    later = (rows["quiz_rank"] > last_rank) & (rows["ts"] > last_ts)
    return win, later


def lift(root, graph, rows, later):
    """(raw lift, difficulty-adjusted lift) or None when D or N has no later answer."""
    if root is None:
        return None
    dep = graph.dependents.get(root, set()) - {root}
    sub = rows["subtopic"][later]
    in_d = np.isin(sub, list(dep))
    in_n = ~in_d & (sub != root)
    if not in_d.any() or not in_n.any():
        return None
    err = 1 - rows["correct"][later]
    resid = rows["pq"][later] - rows["correct"][later]  # (1 - correct) - (1 - M0)
    return float(err[in_d].mean() - err[in_n].mean()), float(resid[in_d].mean() - resid[in_n].mean())


def run(test, graph, bkt, k: int) -> dict:
    """One (k, graph) cell: Unlearn's root vs a random candidate vs BKT's lowest mastery."""
    rng = np.random.default_rng(SEED)
    cands = graph.root_candidates
    res = {m: {} for m in ("unlearn", "random", "bkt")}
    confident_ids, roots, n_diagnosed, n_students = set(), Counter(), 0, 0
    for uid, g in test.groupby("UserId", sort=True):
        n_students += 1
        draw = int(rng.choice(cands))  # one draw per test student, in sorted UserId order
        rows = {"subtopic": g.subtopic.to_numpy(), "ts": g.ts.to_numpy(), "quiz_rank": g.quiz_rank.to_numpy(),
                "correct": g.IsCorrect.to_numpy().astype(float), "pq": g.pq.to_numpy()}
        win, later = split_window(rows, k)
        gs, st = GraphState(), bkt.new_state()
        ws, wc, wt = rows["subtopic"][win], rows["correct"][win].astype(int), rows["ts"][win]
        for i in range(len(ws)):  # same per-answer updates as the walker; only the state after the window is used
            gs.record(IDX[ws[i]], wc[i])
        for t in np.unique(wt):  # BKT through the window, slice by slice
            sl = wt == t
            subs = [IDX[s] for s in ws[sl]]
            bkt.predict(st, subs, [0.0] * len(subs))
            bkt.update(st, subs, wc[sl].tolist())
        targets = {int(s) for s, c in zip(ws, wc) if not c}
        root, conf = diagnose(gs, graph, targets)
        if root is None:
            continue
        n_diagnosed += 1
        roots[root] += 1
        if conf:
            confident_ids.add(uid)
        m = bkt.mastery(st)
        lowest = min(cands, key=lambda s: (m[IDX[s]], s))
        for name, r in (("unlearn", root), ("random", draw), ("bkt", lowest)):
            v = lift(r, graph, rows, later)
            if v is not None:
                res[name][uid] = v
    return summarise(res, confident_ids, roots, n_diagnosed, n_students)


def summarise(res, confident_ids, roots, n_diagnosed, n_students) -> dict:
    out = {"n_test_students": n_students, "n_diagnosed": n_diagnosed,
           "roots": {int(k): v for k, v in sorted(roots.items())}}
    rng = np.random.default_rng(SEED)
    for name, d in res.items():
        ids = sorted(d)
        raw, adj = np.array([d[i][0] for i in ids]), np.array([d[i][1] for i in ids])
        out[name] = {"n_evaluable": len(ids), **_boot(raw, adj, rng)}
        if len(ids) < MIN_EVALUABLE:
            out[name]["underpowered"] = True
    u = res["unlearn"]
    conf_ids = sorted(i for i in u if i in confident_ids)
    out["unlearn_confident"] = {"n_evaluable": len(conf_ids), **_boot(np.array([u[i][0] for i in conf_ids]),
                                                                      np.array([u[i][1] for i in conf_ids]), rng)}
    for other in ("random", "bkt"):
        both = sorted(set(u) & set(res[other]))
        out[f"unlearn - {other}"] = {"n_paired": len(both), **_boot(
            np.array([u[i][0] - res[other][i][0] for i in both]),
            np.array([u[i][1] - res[other][i][1] for i in both]), rng)}
    return out


def _boot(raw: np.ndarray, adj: np.ndarray, rng) -> dict:
    if len(raw) == 0:
        return {"lift": None, "lift_ci": None, "adjusted_lift": None, "adjusted_lift_ci": None}
    idx = rng.integers(0, len(raw), (N_BOOT, len(raw)))
    return {"lift": round(float(raw.mean()), 4), "lift_ci": ci(raw[idx].mean(1)),
            "adjusted_lift": round(float(adj.mean()), 4), "adjusted_lift_ci": ci(adj[idx].mean(1))}
