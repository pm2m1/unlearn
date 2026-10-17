"""The README lists every query in queries.py, and its table matches the generator."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_query_is_in_the_readme():
    spec = importlib.util.spec_from_file_location("readme_queries", ROOT / "scripts" / "readme_queries.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.defined() == mod.documented()
    readme = (ROOT / "README.md").read_text()
    block = readme.split(mod.START, 1)[1].split(mod.END, 1)[0]
    assert block.strip() == mod.table().strip()
    for name in mod.defined():
        assert f"`{name}`" in block
