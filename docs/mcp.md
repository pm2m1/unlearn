# Unlearn MCP server

`api/unlearn/unlearn_mcp.py` exposes Unlearn's fixed graph tools to MCP clients such as Claude Desktop or
Cursor. It is a thin wrapper over `unlearn.tools`. It adds no logic and runs no Cypher of its own.

| Tool | What it returns |
| --- | --- |
| `recall(class_id, student_id)` | Misconceptions the student showed, those on the last diagnosed root cause first, with recent events |
| `root_cause(class_id, student_id, construct_id)` | Deepest unmastered prerequisite with misconception evidence, plus the `REQUIRES` chain |
| `learning_path(class_id, student_id, target_id, to_id?)` | Teaching order, deepest first; with `to_id`, the shortest chain (`algo.SPpaths`) |
| `cohorts(class_id)` | Student groups that share confident misconceptions (`algo.WCC`) |
| `keystones(class_id)` | Top 10 constructs by PageRank over `REQUIRES` |
| `bridges(class_id)` | Constructs where misconceptions cross topics (betweenness on the curriculum graph, seed 42) |
| `propose(class_id, kind, student_ids, payload?, proposal_id?)` | A **pending** Proposal: `regroup`, `skip_ahead` or `assign_practice` |

Every tool returns the receipt `{cypher, params, rows, node_ids}`, so the client can see exactly which
queries produced each answer.

**Not exposed:**
- `decide`. Approving a proposal stays with the human teacher in the UI.
- Any raw Cypher. This is why Unlearn doesn't use FalkorDB's own MCP server: that server runs arbitrary
  queries, while these tools are fixed and parameterised.

`class_id` must name an existing class graph (`class_<id>`). The server refuses anything else, including
`curriculum`.

## Claude Desktop

Prerequisites:
- FalkorDB is running (`make up`).
- The class is seeded (`make seed`).
- `.env` holds `FALKOR_PASSWORD`.

The server reads the repo's `.env` by path, so it doesn't matter which directory Claude Desktop starts it
from.

Add this to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows: `%APPDATA%\Claude\claude_desktop_config.json`), using your own clone's absolute paths:

```json
{
  "mcpServers": {
    "unlearn": {
      "command": "/ABSOLUTE/PATH/TO/unlearn/.venv/bin/python",
      "args": ["-m", "unlearn.unlearn_mcp"],
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/TO/unlearn/api"
      }
    }
  }
}
```

Restart Claude Desktop. Then try:

> Using the unlearn tools on class `demo`, find the cohorts, then propose regrouping the largest one.

The proposal shows up as pending until a teacher approves it in the UI.

## MCP Inspector (no Claude Desktop needed)

The official MCP Inspector runs the same server from the same JSON. Save the config block above to a file, e.g.
`unlearn-mcp.json`, then:

```
npx -y @modelcontextprotocol/inspector@2.9.0 --cli --config unlearn-mcp.json --server unlearn --method tools/list
npx -y @modelcontextprotocol/inspector@2.9.0 --web --config unlearn-mcp.json --server unlearn
```

The first lists the seven tools. The second opens the Inspector's web UI, where you can call `cohorts` and then
`propose` by hand.

## Checking it without a client

`tests/test_mcp.py` starts the server over stdio from `/`, the way Claude Desktop does. It then:
- lists the tools and checks the set is exactly the seven above;
- calls `root_cause` and compares the result with a direct call to the tool function;
- checks that an unknown `class_id` is refused.
