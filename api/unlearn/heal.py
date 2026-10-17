"""Startup self-heal: make sure the graphs the demo needs exist, seeding only what is missing.

  curriculum missing      -> 01_download, 02_load_curriculum, 03_derive, 04_build_template, 05_new_class demo
  class_template missing  -> 04_build_template, 05_new_class demo
  class_demo missing      -> 05_new_class demo

Each step runs the seed script as a subprocess with the same Python, so the API seeds exactly as `make seed`
does. Returns a log of what it found and did.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from unlearn.db import list_graphs

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("unlearn.heal")

FULL = ["01_download.py", "02_load_curriculum.py", "03_derive.py", "04_build_template.py"]
DEMO = ["05_new_class.py", "--id", "demo", "--students", "30"]


def plan(graphs: set[str]) -> list[list[str]]:
    if "curriculum" not in graphs:
        return [[s] for s in FULL] + [DEMO]
    if "class_template" not in graphs:
        return [["04_build_template.py"], DEMO]
    if "class_demo" not in graphs:
        return [DEMO]
    return []


def self_heal() -> list[str]:
    graphs = set(list_graphs())
    steps = plan(graphs)
    lines = [f"graphs found: {sorted(graphs) or 'none'}"]
    if not steps:
        lines.append("nothing to seed")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "api"), str(ROOT)])}
    for step in steps:
        t0 = time.time()
        cmd = [sys.executable, str(ROOT / "scripts" / step[0]), *step[1:]]
        done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        if done.returncode != 0:
            lines.append(f"FAILED {' '.join(step)}: {done.stderr.strip()[-500:]}")
            for line in lines:
                log.error(line)
            raise RuntimeError(f"self-heal failed at {step[0]}")
        lines.append(f"ran {' '.join(step)} in {time.time() - t0:.1f}s")
    lines.append(f"graphs now: {sorted(list_graphs())}")
    for line in lines:
        log.info(line)
    return lines
