# Known FalkorDB issues

[Back to the README](../README.md)

## Known FalkorDB issues we hit (v4.20.7) and the workarounds

| Issue | Workaround |
| --- | --- |
| `ORDER BY length(p)` on a path that isn't returned fails: "Unable to locate a value with alias p" | Return `length(p) AS hops` and order by `hops` (`ROOT_CAUSE_CHAIN`) |
| `ORDER BY` a property not projected after an aggregation fails: "cannot reference variables not projected" | Project it first (`PROPOSALS` returns `created_ts`) |
| `GRAPH.COPY` segfaulted once (signal 11) during rapid delete-and-copy cycles straight after heavy writes. It was not reproducible on its own, even with 60 back-to-back copies | Compose uses `restart: unless-stopped`; the data survived on the volume. `demo_scenario.py` retries the copy once |
| On Render, FalkorDB logged "Possible SECURITY ATTACK detected … Connection from 127.0.0.1 aborted" about every 60 s. It was bound to 127.0.0.1, so the connection came from inside the container, and our code never sends HTTP to it. Redis logs this line when it receives an HTTP request, and one local HTTP request to 127.0.0.1:6379 reproduced it, so it fits Render's port detection probing every listening port | The Render image runs FalkorDB on a unix socket only (`--port 0`, `FALKOR_SOCKET`), so nothing can probe it over TCP. The local compose setup is unchanged |
| `GRAPH.COPY` failed once with "could not fork" while a script was copying a class graph many times in a row. The server was healthy straight after (no save or fork in progress) and the same copy succeeded on retry | `recreate_graph` waits and retries the copy on "could not fork", as it does on "already set" |
| A write query against a graph that was just deleted silently recreates it, empty. Our Teacher worker's polling `CLAIM` did this to test graphs, and once, between a delete and a `GRAPH.COPY` onto that name, it made the copy fail with "key is already set" | Poll with `GRAPH.RO_QUERY` first (`OPEN_TASKS_FOR`) and claim only when a task is waiting. Scripts that rebuild a class run the Teacher themselves, so no task is left waiting, and retry the copy on "already set" |
| The image's default `MAX_QUEUED_QUERIES 25` rejected 60 concurrent simulated students: "Max pending queries exceeded" | Compose sets `FALKORDB_ARGS=MAX_QUEUED_QUERIES 256 TIMEOUT 1000 RESULTSET_SIZE 10000`. It restates the other defaults, because setting the variable replaces them |
| The vector query's `score` is a cosine **distance**: the exact text scores 0.0 | `ORDER BY score ASC`, checked by a test |
| `LIMIT` doesn't limit eager operations that come before it | `CLAIM` limits before it writes; 20 rounds of 10 concurrent claims each have exactly one winner |
| All graphs share one query thread pool, so a saturating load on any class slows every class | A capacity limit rather than a bug; the measured numbers are in [EVALUATION.md](EVALUATION.md) |

Good news: `GRAPH.COPY` carries every index, including the vector index, into the new class graph. `algo.SPpaths`, `algo.WCC`, `algo.pageRank` and seeded `algo.betweenness` all ran unchanged.
