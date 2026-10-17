"""FalkorDB connection, graph selection and query receipts."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from falkordb import FalkorDB

# By path, so a server started from another directory (Claude Desktop) still finds the repo's .env.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@lru_cache(maxsize=1)
def client() -> FalkorDB:
    return FalkorDB(
        host=os.getenv("FALKOR_HOST", "localhost"),
        port=int(os.getenv("FALKOR_PORT", "6379")),
        password=os.getenv("FALKOR_PASSWORD") or None,
    )


def graph(name: str):
    return client().select_graph(name)


def run(graph_name: str, query: str, params: dict | None = None, timeout: int | None = None):
    """Run a parameterised query. Returns (rows, receipt).

    rows is a list of dicts keyed by the RETURN aliases.
    receipt is {cypher, params, rows} so callers can show what proved a claim.
    """
    params = params or {}
    result = graph(graph_name).query(query, params, timeout=timeout)
    columns = [h[1] for h in result.header]
    rows = [dict(zip(columns, record)) for record in result.result_set]
    receipt = {"cypher": query, "params": params, "rows": rows}
    return rows, receipt


def run_batched(graph_name: str, query: str, rows: list[dict], batch_size: int = 500, timeout: int | None = None):
    """Run an `UNWIND $rows` query in batches. Returns the number of batches sent."""
    batches = 0
    for start in range(0, len(rows), batch_size):
        run(graph_name, query, {"rows": rows[start:start + batch_size]}, timeout=timeout)
        batches += 1
    return batches


def list_graphs() -> list[str]:
    return client().list_graphs()


def delete_graph(name: str) -> bool:
    """Delete a graph if it exists. Returns True if something was deleted."""
    if name in list_graphs():
        graph(name).delete()
        return True
    return False


def copy_graph(src: str, dst: str) -> None:
    """GRAPH.COPY src dst. dst must not exist."""
    graph(src).copy(dst)


def create_indexes(graph_name: str, statements: list[str]) -> None:
    """Run CREATE INDEX statements, skipping ones that already exist."""
    from redis.exceptions import ResponseError

    for stmt in statements:
        try:
            run(graph_name, stmt)
        except ResponseError as e:
            if "already indexed" not in str(e):
                raise
