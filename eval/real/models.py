"""Task A models and the time-respecting walker they all run through (PREREGISTRATION.md sections 2, 4, 5).

walk() visits each student's answers in (ts, AnswerId) order, one time slice (all answers sharing a ts) at a
time. For a slice it first calls model.predict with only the slice's SubTopics and question difficulties, never
their outcomes, then model.update with the outcomes. So every prediction is made from strictly earlier answers,
and answers in one block never see each other. The walker also asserts this (the state's latest ts < the slice's).
"""

import math

import numpy as np

from eval.real.data import SUBTOPICS
from unlearn.tools import MASTERY_CORRECT, MASTERY_MAX_CONFIDENCE

IDX = {s: i for i, s in enumerate(SUBTOPICS)}
K = len(SUBTOPICS)


# --- walker -------------------------------------------------------------------

def walk(df, model, width: int = 1) -> np.ndarray:
    """Predictions (n, width) in df's row order. df must be sorted by UserId, ts, AnswerId."""
    users, ts = df.UserId.to_numpy(), df.ts.to_numpy()
    sub = [IDX[s] for s in df.subtopic.to_numpy()]
    pq = df.pq.to_numpy().tolist()
    correct = df.IsCorrect.to_numpy().tolist()
    out = np.empty((len(df), width))
    starts = np.flatnonzero(np.r_[True, users[1:] != users[:-1]])
    ends = np.r_[starts[1:], len(df)]
    slice_starts = np.flatnonzero(np.r_[True, (users[1:] != users[:-1]) | (ts[1:] != ts[:-1])])
    slice_ends = np.r_[slice_starts[1:], len(df)]
    k = 0
    for a, b in zip(starts, ends):
        st, seen_ts = model.new_state(), -1
        while k < len(slice_starts) and slice_starts[k] < b:
            i, j = slice_starts[k], slice_ends[k]
            assert seen_ts < ts[i], "leak: state includes an answer at or after this slice's ts"
            out[i:j] = np.asarray(model.predict(st, sub[i:j], pq[i:j]), dtype=float).reshape(j - i, width)
            model.update(st, sub[i:j], correct[i:j])
            seen_ts = ts[i]
            k += 1
    return out[:, 0] if width == 1 else out


# --- M0, M0b ------------------------------------------------------------------

def question_difficulty(train) -> tuple[dict, float]:
    """M0: (correct + 1) / (answers + 2) per question on train; unseen questions get the train correct rate."""
    g = train.groupby("QuestionId").IsCorrect.agg(["sum", "count"])
    return ((g["sum"] + 1) / (g["count"] + 2)).to_dict(), float(train.IsCorrect.mean())


class M0:
    def new_state(self):
        return None

    def predict(self, st, subs, pqs):
        return pqs

    def update(self, st, subs, correct):
        pass


class M0b:
    """(earlier right on X + 2 p_X) / (earlier answers on X + 2)."""

    def __init__(self, p_sub: list[float]):
        self.p = p_sub

    def new_state(self):
        return [[0, 0] for _ in range(K)]

    def predict(self, st, subs, pqs):
        return [(st[x][0] + 2 * self.p[x]) / (st[x][1] + 2) for x in subs]

    def update(self, st, subs, correct):
        for x, c in zip(subs, correct):
            st[x][0] += c
            st[x][1] += 1


# --- correctness-only graph state (section 4) ---------------------------------

def evidence(wrong: int) -> float:
    """count x confidence x w with w = 1 and confidence = 1 - 0.5^count (production UPDATE_SHOWED)."""
    return wrong * (1 - 0.5 ** wrong) if wrong else 0.0


class GraphState:
    """wrong/right counts and permanent MASTERED per SubTopic, updated per answer as in record_attempt."""

    __slots__ = ("wrong", "right", "mastered")

    def __init__(self):
        self.wrong, self.right, self.mastered = [0] * K, [0] * K, [False] * K

    def record(self, x: int, c: int) -> None:
        if c:
            self.right[x] += 1
        else:
            self.wrong[x] += 1
        conf = 1 - 0.5 ** self.wrong[x] if self.wrong[x] else 0.0
        if not self.mastered[x] and self.right[x] >= MASTERY_CORRECT and conf <= MASTERY_MAX_CONFIDENCE:
            self.mastered[x] = True


def root_cause_rows(gs: GraphState, graph, target: int) -> list[tuple[int, int, float]]:
    """ROOT_CAUSE on the SubTopic graph: (prereq SubTopic, depth, evidence), evidence desc then depth desc."""
    rows = []
    for p, d in graph.prereqs.get(target, {}).items():
        x = IDX[p]
        ev = evidence(gs.wrong[x])
        if not gs.mastered[x] and ev > 0:
            rows.append((p, d, ev))
    return sorted(rows, key=lambda r: (-r[2], -r[1]))


def suspicion(gs: GraphState, graph, target: int) -> float:
    """Top evidence of root_cause(target), 0 if none."""
    rows = root_cause_rows(gs, graph, target)
    return rows[0][2] if rows else 0.0


class GraphFeatures:
    """M2's features at prediction time: logit(M0), evidence at X, mastered X, prerequisite suspicion."""

    def __init__(self, graph):
        self.graph = graph

    def new_state(self):
        return GraphState()

    def predict(self, gs, subs, pqs):
        out = []
        for x, p in zip(subs, pqs):
            p = min(max(p, 1e-6), 1 - 1e-6)
            out.append((math.log(p / (1 - p)), evidence(gs.wrong[x]), float(gs.mastered[x]),
                        suspicion(gs, self.graph, SUBTOPICS[x])))
        return out

    def update(self, gs, subs, correct):
        for x, c in zip(subs, correct):
            gs.record(x, c)


# --- BKT (M1) and BKT + graph prior (M3) --------------------------------------

class BKT:
    """Plain 4-parameter BKT per SubTopic. params[x] = (L0, T, S, G). With beta > 0 (M3), a student's L0 for X is
    set at their first block on X to L0 * exp(-beta * prerequisite suspicion at that time)."""

    def __init__(self, params: list[tuple], beta: float = 0.0, graph=None):
        self.params, self.beta, self.graph = params, beta, graph

    def new_state(self):
        return {"pL": [None] * K, "gs": GraphState() if self.beta else None}

    def predict(self, st, subs, pqs):
        pL = st["pL"]
        for x in subs:
            if pL[x] is None:
                L0 = self.params[x][0]
                pL[x] = L0 * math.exp(-self.beta * suspicion(st["gs"], self.graph, SUBTOPICS[x])) if self.beta else L0
        return [pL[x] * (1 - self.params[x][2]) + (1 - pL[x]) * self.params[x][3] for x in subs]

    def update(self, st, subs, correct):
        pL = st["pL"]
        for x, c in zip(subs, correct):
            L0, T, S, G = self.params[x]
            p = pL[x] if pL[x] is not None else L0
            post = p * (1 - S) / (p * (1 - S) + (1 - p) * G) if c else p * S / (p * S + (1 - p) * (1 - G))
            pL[x] = post + (1 - post) * T
            if st["gs"] is not None:
                st["gs"].record(x, c)

    def mastery(self, st) -> list[float]:
        """P(L) per SubTopic after everything seen (L0 where unobserved)."""
        return [st["pL"][x] if st["pL"][x] is not None else self.params[x][0] for x in range(K)]


MAX_GUESS = MAX_SLIP = 0.5  # identifiability (PREREGISTRATION.md deviation 7): never "learned" meaning worse


def fit_bkt(seqs: list[np.ndarray], init=(0.4, 0.1, 0.1, 0.2), max_iter: int = 200, tol: float = 1e-6) -> dict:
    """EM (Baum-Welch) for one skill's 2-state HMM, vectorised over left-aligned padded sequences.
    The M-step caps guess and slip at 0.5."""
    n, T = len(seqs), max(len(s) for s in seqs)
    obs, mask = np.zeros((n, T)), np.zeros((n, T), bool)
    for i, s in enumerate(seqs):
        obs[i, : len(s)], mask[i, : len(s)] = s, True
    L0, Tr, S, G = init
    lls, prev_ll = [], None
    for it in range(max_iter):
        e1 = np.where(mask, np.where(obs == 1, 1 - S, S), 1.0)  # P(obs | learned); 1 on padding
        e0 = np.where(mask, np.where(obs == 1, G, 1 - G), 1.0)  # P(obs | not learned)
        a, c = np.empty((n, T, 2)), np.empty((n, T))
        p0, p1 = np.full(n, 1 - L0), np.full(n, L0)
        for t in range(T):
            if t:
                p0, p1 = a[:, t - 1, 0] * (1 - Tr), a[:, t - 1, 0] * Tr + a[:, t - 1, 1]
            f0, f1 = p0 * e0[:, t], p1 * e1[:, t]
            c[:, t] = f0 + f1
            a[:, t, 0], a[:, t, 1] = f0 / c[:, t], f1 / c[:, t]
        ll = float(np.log(c).sum())
        lls.append(ll)
        b = np.ones((n, T, 2))
        for t in range(T - 2, -1, -1):
            n0, n1 = e0[:, t + 1] * b[:, t + 1, 0], e1[:, t + 1] * b[:, t + 1, 1]
            b[:, t, 0] = ((1 - Tr) * n0 + Tr * n1) / c[:, t + 1]
            b[:, t, 1] = n1 / c[:, t + 1]
        g = a * b
        xi01 = a[:, :-1, 0] * Tr * e1[:, 1:] * b[:, 1:, 1] / c[:, 1:]
        mt = mask[:, 1:]
        L0 = float(g[:, 0, 1].mean())
        Tr = float((xi01 * mt).sum() / (g[:, :-1, 0] * mt).sum())
        G = min(float((g[..., 0] * obs * mask).sum() / (g[..., 0] * mask).sum()), MAX_GUESS)
        S = min(float((g[..., 1] * (1 - obs) * mask).sum() / (g[..., 1] * mask).sum()), MAX_SLIP)
        if prev_ll is not None and abs(ll - prev_ll) < tol:
            break
        prev_ll = ll
    return {"params": (L0, Tr, S, G), "iterations": it + 1, "loglik": lls}


def bkt_sequences(train) -> list[list[np.ndarray]]:
    """Per SubTopic index: each train student's outcomes on it, in (ts, AnswerId) order."""
    seqs = [[] for _ in range(K)]
    for (_, s), grp in train.groupby(["UserId", "subtopic"], sort=False):
        seqs[IDX[s]].append(grp.IsCorrect.to_numpy())
    return seqs
