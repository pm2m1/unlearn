"""MCP server over the domain tools (SPEC "MCP server").

Exposes recall, root_cause, learning_path, cohorts, keystones, bridges and propose. Every tool takes
class_id. Not exposed: decide (approval stays with the human teacher) and any raw Cypher. Each tool
wraps the function in unlearn.tools and adds no logic beyond checking that the class graph exists.

Run:  PYTHONPATH=api python -m unlearn.unlearn_mcp   (stdio transport; docs/mcp.md has the client config)
"""

import re

from mcp.server.fastmcp import FastMCP

from unlearn import tools
from unlearn.db import list_graphs

mcp = FastMCP("unlearn")

_CLASS_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _class(class_id: str) -> str:
    """Only existing class graphs: an MCP client can't reach `curriculum` or invent a graph name."""
    if not _CLASS_ID.match(class_id) or tools.graph_name(class_id) not in list_graphs():
        raise ValueError(f"no class graph for class_id {class_id!r}")
    return class_id


@mcp.tool()
def recall(class_id: str, student_id: str) -> dict:
    """What the tutor remembers about a student: misconceptions shown with confidence > 0.6, newest first, with recent events."""
    return tools.recall(_class(class_id), student_id)


@mcp.tool()
def root_cause(class_id: str, student_id: str, construct_id: int) -> dict:
    """Deepest unmastered prerequisite with misconception evidence, plus the REQUIRES chain."""
    return tools.root_cause(_class(class_id), student_id, construct_id)


@mcp.tool()
def learning_path(class_id: str, student_id: str, target_id: int, to_id: int | None = None) -> dict:
    """Teaching order, deepest first, for every unmastered construct the target depends on. With to_id, also the shortest REQUIRES chain to it."""
    return tools.learning_path(_class(class_id), student_id, target_id, to_id)


@mcp.tool()
def cohorts(class_id: str) -> dict:
    """Groups of students who share confident misconceptions (rebuilds SHARES_GAP edges, then WCC)."""
    return tools.cohorts(_class(class_id))


@mcp.tool()
def keystones(class_id: str) -> dict:
    """PageRank over REQUIRES: the 10 constructs most of the topic depends on."""
    return tools.keystones(_class(class_id))


@mcp.tool()
def bridges(class_id: str) -> dict:
    """Constructs where misconceptions leak across topics (betweenness on the shared curriculum graph, fixed seed)."""
    _class(class_id)
    return tools.bridges()


@mcp.tool()
def propose(class_id: str, kind: str, student_ids: list[str], payload: dict | None = None,
            proposal_id: str | None = None) -> dict:
    """Write a pending Proposal for the teacher to approve or reject in the UI. kind is regroup (2+ students),
    skip_ahead or assign_practice (both need payload {"construct_id": int}). Nothing changes until approved."""
    pid = proposal_id or f"p-mcp-{tools.now_ms()}"
    return tools.propose(_class(class_id), pid, kind, payload or {}, student_ids)


if __name__ == "__main__":
    mcp.run()
