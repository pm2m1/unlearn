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


def run(graph_name: str, query: str, params: dict | None = None, timeout: int | None = None,
        read_only: bool = False):
    """Run a parameterised query. Returns (rows, receipt). read_only uses GRAPH.RO_QUERY, which never writes
    and never creates a graph that doesn't exist.

    rows is a list of dicts keyed by the RETURN aliases.
    receipt is {cypher, params, rows} so callers can show what proved a claim.
    """
    params = params or {}
    g = graph(graph_name)
    result = g.ro_query(query, params, timeout=timeout) if read_only else g.query(query, params, timeout=timeout)
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


def recreate_graph(src: str, dst: str, attempts: int = 3) -> bool:
    """Delete dst (if any) and GRAPH.COPY src onto it. Returns True if dst existed before.

    Any write to a deleted graph recreates it, so a worker polling class graphs (the API's Teacher) can bring dst
    back between the delete and the copy, and the copy then fails with "key is already set". Delete and copy again.
    GRAPH.COPY also forks the server, and once failed with "could not fork" (README: known issues): wait, retry.
    """
    import time

    from redis.exceptions import ResponseError

    existed = False
    for attempt in range(1, attempts + 1):
        existed = delete_graph(dst) or existed
        try:
            copy_graph(src, dst)
            return existed
        except ResponseError as e:
            if not ("already set" in str(e) or "could not fork" in str(e)) or attempt == attempts:
                raise
            if "could not fork" in str(e):
                time.sleep(attempt)
    return existed


def create_indexes(graph_name: str, statements: list[str]) -> None:
    """Run CREATE INDEX statements, skipping ones that already exist."""
    from redis.exceptions import ResponseError

    for stmt in statements:
        try:
            run(graph_name, stmt)
        except ResponseError as e:
            if "already indexed" not in str(e):
                raise
