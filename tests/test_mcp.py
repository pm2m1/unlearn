"""The MCP server over stdio: list its tools and call root_cause, as Claude Desktop would."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from conftest import build_class
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from unlearn import tools as T
from unlearn.db import delete_graph

ROOT = Path(__file__).resolve().parents[1]
CLASS_ID = "pytest_mcp"
EXPOSED = {"recall", "root_cause", "learning_path", "cohorts", "keystones", "bridges", "propose"}


@pytest.fixture(scope="module")
def mcp_class():
    build_class(f"class_{CLASS_ID}")
    T.start_session(CLASS_ID, "sa", "sa-1", ts=1)
    for i, q in enumerate(("q-3-1", "q-3-2"), start=2):  # Asha shows 301 twice on construct 3
        T.record_attempt(CLASS_ID, "sa", q, "B", "sa-1", ts=i)
    yield CLASS_ID
    delete_graph(f"class_{CLASS_ID}")


async def _session(calls):
    params = StdioServerParameters(command=sys.executable, args=["-m", "unlearn.unlearn_mcp"],
                                   env={**os.environ, "PYTHONPATH": str(ROOT / "api")}, cwd="/")  # like Claude Desktop
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await calls(session)


def _payload(result) -> dict:
    assert not result.isError, result.content
    return json.loads(result.content[0].text)


def test_lists_exactly_the_exposed_tools(mcp_class):
    async def calls(s):
        return await s.list_tools()
    listed = asyncio.run(_session(calls)).tools
    assert {t.name for t in listed} == EXPOSED  # no decide, no raw Cypher
    assert all("class_id" in t.inputSchema["properties"] for t in listed)


def test_root_cause_over_stdio_matches_the_tool(mcp_class):
    async def calls(s):
        return await s.call_tool("root_cause", {"class_id": mcp_class, "student_id": "sa", "construct_id": 1})
    out = _payload(asyncio.run(_session(calls)))
    assert set(out) == {"cypher", "params", "rows", "node_ids"}
    assert out["rows"][0]["id"] == 3 and out["rows"][0]["chain_ids"] == [1, 2, 3]
    assert out["rows"] == T.root_cause(mcp_class, "sa", 1)["rows"]


def test_unknown_class_is_refused(mcp_class):
    async def calls(s):
        return await s.call_tool("recall", {"class_id": "nope", "student_id": "sa"})
    assert asyncio.run(_session(calls)).isError
