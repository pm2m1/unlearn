"""AUC, log-loss, accuracy, and the paired student-level bootstrap (PREREGISTRATION.md section 5)."""

import numpy as np

N_BOOT = 1000
SEED = 0
CLIP = 1e-6


class AUC:
    """Weighted AUC (ties count half) for one score vector; weights are per row, so a bootstrap is a bincount."""

    def __init__(self, scores: np.ndarray, y: np.ndarray):
        uniq, self.group = np.unique(scores, return_inverse=True)  # groups in ascending score order
        self.ng, self.y = len(uniq), y.astype(float)

    def __call__(self, w: np.ndarray) -> float:
        pos = np.bincount(self.group, w * self.y, self.ng)
        neg = np.bincount(self.group, w * (1 - self.y), self.ng)
        below = np.cumsum(neg) - neg
        return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))


def row_loss(p, y):
    p = np.clip(p, CLIP, 1 - CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def logloss(p, y, w):
    return float((w * row_loss(p, y)).sum() / w.sum())


def accuracy(p, y, w):
    return float((w * ((p >= 0.5) == (y == 1))).sum() / w.sum())


def resample_weights(students: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED):
    """Yields per-row weights: each resample draws the students with replacement, a row weighs its student's count."""
    uniq, idx = np.unique(students, return_inverse=True)
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        counts = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        yield counts[idx].astype(float)


def ci(values) -> list[float]:
    return [round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)]


def evaluate(preds: dict[str, np.ndarray], y: np.ndarray, students: np.ndarray, subsets: dict[str, np.ndarray],
             pairs: list[tuple[str, str]], contrasts: list[tuple[str, str, str, str]] = ()) -> dict:
    """Point estimates and 95% intervals per subset (a boolean row mask) and model; paired AUC differences for
    `pairs`; and `contrasts` (a, b, subset1, subset2): (a - b on subset1) - (a - b on subset2). One set of
    student resamples is shared by everything, so all differences are paired."""
    out, auc, rows = {}, {}, {}
    for s, mask in subsets.items():
        ys, ones = y[mask], np.ones(int(mask.sum()))
        out[s] = {"n_answers": int(mask.sum()), "n_students": int(len(np.unique(students[mask]))), "models": {},
                  "differences": {}}
        for m, p in preds.items():
            ps = p[mask]
            auc[s, m] = AUC(ps, ys)
            rows[s, m] = (row_loss(ps, ys), (ps >= 0.5) == (ys == 1))
            out[s]["models"][m] = {"auc": round(auc[s, m](ones), 4), "logloss": round(float(rows[s, m][0].mean()), 4),
                                   "accuracy": round(float(rows[s, m][1].mean()), 4)}
    boot = {(s, m, k): [] for s in subsets for m in preds for k in ("auc", "logloss", "accuracy")}
    for w in resample_weights(students):
        for s, mask in subsets.items():
            ws = w[mask]
            for m in preds:
                boot[s, m, "auc"].append(auc[s, m](ws))
                boot[s, m, "logloss"].append(float(ws @ rows[s, m][0] / ws.sum()))
                boot[s, m, "accuracy"].append(float(ws @ rows[s, m][1] / ws.sum()))
    for (s, m, k), v in boot.items():
        out[s]["models"][m][k + "_ci"] = ci(v)
    d = lambda s, a, b: np.array(boot[s, a, "auc"]) - np.array(boot[s, b, "auc"])
    full = {k: a(np.ones(int(subsets[k[0]].sum()))) for k, a in auc.items()}  # unrounded point AUCs
    point = lambda s, a, b: full[s, a] - full[s, b]
    for s in subsets:
        for a, b in pairs:
            diff, (lo, hi) = round(point(s, a, b), 4), ci(d(s, a, b))
            out[s]["differences"][f"{a} - {b}"] = {"auc_diff": diff, "ci": [lo, hi], "verdict": verdict(diff, lo, hi)}
    out["contrasts"] = {}
    for a, b, s1, s2 in contrasts:
        diff = round(point(s1, a, b) - point(s2, a, b), 4)
        out["contrasts"][f"({a} - {b}) on {s1} minus on {s2}"] = {"auc_diff": diff, "ci": ci(d(s1, a, b) - d(s2, a, b))}
    return out


def verdict(diff: float, lo: float, hi: float, min_effect: float = 0.005) -> str:
    """Section 5's wording: better / worse / negligible / no detectable difference."""
    if lo <= 0 <= hi:
        return "no detectable difference"
    if abs(diff) < min_effect:
        return "negligible"
    return "better" if diff > 0 else "worse"
