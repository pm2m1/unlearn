"""Draw docs/img/graph-model.png: Unlearn's graph model, with Asha's root-cause path in amber.

    python docs/graph_model.py        # needs matplotlib (a docs-only dependency, not in requirements.txt)

Node and relationship names are the real ones from the README's data model. The amber nodes and edges are Asha's
data in class_demo_video: her fractions check showed "Thinks you add the numerators and add the denominators"
twice, which is SEEN_IN construct 429; 429 REQUIRES 427 REQUIRES 345, where her diagnosis session showed "Finds a
common multiple but not the lowest" (SEEN_IN 345, weight 1.0), so root_cause names 345. Grey edges are the other
relationship types in the model, drawn for one example each, not Asha's data.
"""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent / "img" / "graph-model.png"
AMBER, AMBER_SOFT, AMBER_INK = "#e3a33b", "#fdf3e2", "#6b4405"
RED, RED_SOFT, RED_INK = "#d2453f", "#fbeceb", "#9a2d28"
GREEN_SOFT, INK, MUTED, LINE, PAPER, BG = "#e8f5ee", "#1b1d22", "#6c707a", "#b9bcc4", "#ffffff", "#f6f5f1"
W, H = 12.0, 8.2

nodes = {  # key: (x, y, width, label, name, style)
    "proposal": (1.55, 6.55, 2.6, "Proposal", "assign practice on the root cause\n(waits for the teacher)", "plain"),
    "asha":     (1.55, 4.65, 2.6, "Student", "Asha", "amber"),
    "session":  (1.55, 2.55, 2.6, "Session", "Asha's session 1", "plain"),
    "event":    (1.55, 0.75, 2.6, "Event", "diagnosis: root cause found", "plain"),
    "m1":       (5.1, 5.75, 3.2, "Misconception", "Thinks you add the numerators and add the denominators when adding fractions", "mis"),
    "m2":       (5.1, 3.15, 3.2, "Misconception", "Finds a common multiple but not the lowest common multiple", "mis"),
    "question": (9.35, 0.75, 3.6, "Question / Option", "q-345-3: lowest common multiple · option D \"48\"", "plain"),
    "c429":     (9.35, 6.55, 3.6, "Construct (skill) · topic", "Add fractions involving mixed number fractions with different denominators", "amber"),
    "c427":     (9.35, 4.7, 3.6, "Construct (skill)", "Add proper fractions with different denominators which do not share a common factor", "amber"),
    "c345":     (9.35, 2.75, 3.6, "Construct · ROOT CAUSE", "Identify the Lowest Common Multiple of two numbers", "root"),
    "c342":     (5.1, 0.75, 3.2, "Construct (skill)", "Identify multiples of a number", "plain"),
}

edges = [  # (src, dst, label, amber, label position along the edge, curve)
    ("asha", "m1", "SHOWED ×2", True, 0.5, 0.0),
    ("m1", "c429", "SEEN_IN", True, 0.5, 0.0),
    ("c429", "c427", "REQUIRES", True, 0.5, 0.0),
    ("c427", "c345", "REQUIRES", True, 0.5, 0.0),
    ("asha", "m2", "SHOWED", True, 0.45, 0.0),
    ("m2", "c345", "SEEN_IN", True, 0.5, 0.0),
    ("c345", "c342", "REQUIRES", False, 0.5, 0.0),
    ("proposal", "asha", "FOR", False, 0.5, 0.0),
    ("asha", "session", "HAD_SESSION", False, 0.5, 0.0),
    ("session", "event", "HAD_EVENT", False, 0.5, 0.0),
    ("event", "c345", "ABOUT", False, 0.36, 0.0),
    ("question", "m2", "Option INDICATES", False, 0.5, 0.0),
    ("question", "c345", "Question ASSESSES", False, 0.5, 0.0),
    ("asha", "c342", "MASTERED (once shown)", False, 0.55, 0.0),
]


def box(ax, key):
    x, y, w, label, name, style = nodes[key]
    lines = textwrap.wrap(name, 34 if w > 3 else 30)
    h = 0.36 + 0.24 * len(lines)
    face, edge, lw, ink = {"amber": (AMBER_SOFT, AMBER, 2.2, AMBER_INK), "root": (AMBER_SOFT, AMBER, 4.5, AMBER_INK),
                           "mis": (RED_SOFT, RED, 1.6, RED_INK), "plain": (PAPER, LINE, 1.3, INK)}[style]
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=face, ec=edge, lw=lw, zorder=3))
    ax.text(x, y + h / 2 - 0.2, label.upper(), ha="center", va="center", fontsize=7.6, color=MUTED if style == "plain" else ink,
            fontweight="bold", zorder=4)
    ax.text(x, y - 0.11, "\n".join(lines), ha="center", va="center", fontsize=9.2, color=ink if style != "plain" else INK,
            linespacing=1.25, zorder=4, fontweight="bold" if style in ("amber", "root") else "normal")
    nodes[key] = (x, y, w, label, name, style, h)


def anchor(key, toward):
    x, y, w, *_, h = nodes[key]
    tx, ty = nodes[toward][0], nodes[toward][1]
    dx, dy = tx - x, ty - y
    if abs(dx) * h > abs(dy) * w:  # leaves through a side
        return x + (w / 2) * (1 if dx > 0 else -1), y + dy * (w / 2) / abs(dx) * 0.6
    return x + dx * (h / 2) / abs(dy) * 0.6, y + (h / 2) * (1 if dy > 0 else -1)


def arrow(ax, src, dst, label, amber, t, rad):
    (x1, y1), (x2, y2) = anchor(src, dst), anchor(dst, src)
    color = AMBER if amber else "#9aa0ab"
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=3.0 if amber else 1.3,
                                 color=color, connectionstyle=f"arc3,rad={rad}", zorder=2,
                                 linestyle="solid" if amber or "MASTERED" not in label else (0, (4, 3))))
    # the label sits on the drawn curve: arc3's quadratic Bezier, control point as matplotlib places it
    cx, cy = (x1 + x2) / 2 + rad * (y2 - y1), (y1 + y2) / 2 - rad * (x2 - x1)
    mx = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
    my = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
    ax.text(mx, my, label, ha="center", va="center", fontsize=8.2, color=AMBER_INK if amber else MUTED,
            fontweight="bold" if amber else "normal", zorder=5,
            bbox=dict(boxstyle="round,pad=0.18", fc=BG, ec="none"))


def main() -> int:
    fig = plt.figure(figsize=(W, H), dpi=100, facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1)); ax.set_xlim(0, W); ax.set_ylim(-0.25, H - 0.25); ax.axis("off")
    for k in list(nodes):
        box(ax, k)
    for e in edges:
        arrow(ax, *e)
    ax.text(0.3, H - 0.47, "Unlearn's graph model, with Asha's root-cause path", fontsize=15, fontweight="bold",
            color=INK, family="serif")
    ax.text(0.3, H - 0.82, "Amber: Asha's data in class_demo_video. Grey: the model's other relationship types, one example each.",
            fontsize=9.5, color=MUTED)
    fig.savefig(OUT, facecolor=BG)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
