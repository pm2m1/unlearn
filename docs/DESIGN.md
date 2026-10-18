# Design

[Back to the README](../README.md)

## How the agents work

- **Diagnoser.** Opens with `recall`, then asks adaptive questions. It searches top-down over `REQUIRES`: a right answer rules out that skill and everything below it, and a wrong answer makes it a suspect to search beneath. It stops when `root_cause` is confident. Every step's state lives in the graph (`Task`, this session's `ATTEMPTED` edges), so each HTTP request runs exactly one step.
- **Tutor.** Explains the root cause with the remediation skill that has worked best so far, asks one check question, and updates that skill's success rate. If the student is still stuck, it hands off to the Teacher agent.
- **Teacher agent.** Looks at cohorts (WCC), keystones (PageRank) and bridges (betweenness), then writes a **Proposal**. Nothing changes until a human approves it. On approval, an executor applies the change from the graph's own edges and logs an `Event`.
- **Receipts everywhere.** Every tool call returns `{cypher, params, rows, node_ids}`. The UI's drawer shows them, and the LLM's words are rejected if they name a construct or misconception that isn't in that turn's rows.
- **The LLM writes words, never facts.**
  - **The chain:** Gemini (`gemini-3.8-flash`, thinking off) → OpenRouter → Groq → template. Each provider is skipped when it has no key.
  - **Checked replies:** a reply must pass the receipt check, have at least 8 words and no bare list markers. A reply that fails gets one retry, then the template takes over.
  - **Free-tier limit:** Gemini's free tier allows 20 requests per model per day. A busy demo uses that up within a few sessions, after which every reply is a template. Nothing breaks, but the wording becomes plainer.

## Design decisions worth knowing
- **Stop thresholds.** The Diagnoser stops when the top root-cause evidence is ≥ 1.5 and leads the runner-up by ≥ 0.5. These are the SPEC's original values, and they follow from the evidence scale: the median prerequisite distractor has weight 1.0, so two hits score 1.5. Looser thresholds (1.0 / 0.33) named the planted root slightly more often on the simulator: 104/115/119 against 102/110/113 of the 139 (root, target) pairs on seeds 0–2 (`eval/design_checks.py`, [`design_checks.json`](../eval/results/design_checks.json)). They were not adopted, so the thresholds aren't tuned to the simulator the eval scores against. An earlier version of this note gave 109/126/126 against 103/121/121 of 151; those came from earlier code on the pre-review data.
- **Recall.** `recall` returns every misconception the student has shown. It ranks those on the root cause the student was diagnosed with last session first, then the strongest, then the most recent.
  - **Why it changed:** the build spec kept only misconceptions seen at least twice. That left 58 of 90 simulated students with nothing to recall in session 2.
  - **Chosen after seeing the eval results:** three rules were measured on the same session-1 histories, and "last diagnosed root first" was picked afterwards. The tutor should open with what it diagnosed last session, and that rule does exactly that.
  - **The cost:** fewer of the named misconceptions are right than under the original rule, because one-off slips get named too.

  Measured by `eval/design_checks.py` on the eval's 90 students ([`design_checks.json`](../eval/results/design_checks.json)):

  | `recall` rule | Session-2 opening names a planted misconception | Named misconceptions that were planted |
  | --- | --- | --- |
  | Seen twice (confidence > 0.6), newest first (build spec) | 28% | 78% |
  | Seen once or more, strongest first | 56% | 31% |
  | Seen once or more, last diagnosed root first (**current**) | 68% | 45% |

## Graph data model (full schema)

Three kinds of graph live in one FalkorDB instance:
- `curriculum`: the full Eedi graph, read-only.
- `class_template`: the Fractions slice plus the curated edges, questions and skills.
- `class_<id>`: one per classroom, made with `GRAPH.COPY`, which carries all 9 indexes, including the vector index.

FalkorDB serialises writes per graph, so classes don't queue behind each other's writes (measured in [EVALUATION.md](EVALUATION.md)).

![Unlearn's graph model, with Asha's root-cause path in amber](img/graph-model.png)

*Amber is Asha's real path: she `SHOWED` a misconception `SEEN_IN` the topic, which `REQUIRES` two levels down to the lowest common multiple, where her diagnosis found the evidence. Grey shows the model's other relationship types. Drawn by [`docs/graph_model.py`](graph_model.py).*

```
// Curriculum (in curriculum and class graphs)
(:Subject {id,name})-[:HAS_TOPIC]->(:Topic {id,name})-[:HAS_SUBTOPIC]->(:SubTopic {id,name})-[:HAS_CONSTRUCT]->(:Construct {id,name,pagerank})
(:Misconception {id,name,embedding})-[:SEEN_IN {pct, w}]->(:Construct)   // w: share of the misconception's pct within the class slice
(:Construct)-[:REQUIRES {source:'curated', weight:1}]->(:Construct)   // (needs)-[:REQUIRES]->(prerequisite)
(:Construct)-[:SHARES_MISCONCEPTION {n}]->(:Construct)                 // curriculum graph only, derived

// Assessment (class graphs)
(:Question {id,text})-[:ASSESSES]->(:Construct)
(:Option {qid,key,text,correct})-[:OPTION_OF]->(:Question)
(:Option)-[:INDICATES]->(:Misconception)                               // wrong options only

// Memory (class graphs)
(:Student {id,alias})-[:ATTEMPTED {ts,session,option,correct}]->(:Question)
(:Student)-[:SHOWED {count,confidence,first_ts,last_ts}]->(:Misconception)
(:Student)-[:MASTERED {ts,evidence}]->(:Construct)
(:Student)-[:HAD_SESSION]->(:Session {id,ts,n})-[:HAD_EVENT]->(:Event {id,type,ts,summary})
(:Event)-[:ABOUT]->(:Misconception|:Construct)
(:Skill {name,success_rate,uses})-[:REMEDIATES]->(:Misconception)
(:Skill)-[:HAS_STEP {order}]->(:Step {text})

// Coordination (class graphs)
(:Agent {name})                                                        // Diagnoser, Tutor, Teacher
(:Task {id,kind,state,claimed_by,created_ts,construct_id,session})-[:ABOUT]->(:Student)
(:Task)-[:ASSIGNED_TO]->(:Agent)
(:Task)-[:HANDED_OFF_FROM]->(:Task)
(:Proposal {id,kind,state,payload})-[:FOR]->(:Student)                  // waits for teacher approval
(:Proposal)-[:SUPERSEDED_BY]->(:Proposal)                              // a larger regroup replaced a pending one
(:Proposal)-[:HAD_EVENT]->(:Event)                                     // logged when an approval is applied
(:Group {id})-[:HAS_MEMBER]->(:Student)                                // applied regroup
(:Assignment {id,ts,proposal})-[:FOR]->(:Student), (:Assignment)-[:PRACTICES]->(:Construct)
(:Student)-[:SHARES_GAP {miscs}]->(:Student)                            // derived for cohorts
```

| Memory type (Track 02) | Where it lives | Example |
| --- | --- | --- |
| Episodic | `Session`, `Event`, `ATTEMPTED` | "On Oct 17 Asha picked C on q-345-2" |
| Semantic | `SHOWED`, `MASTERED` | "Asha finds a common multiple but not the lowest" |
| Procedural | `Skill` → `Step`, with `success_rate` | "LCM-first common denominators worked 3 of 4 times" |
| Shared state | `Task`, `Proposal` | "Diagnoser handed Asha to the Tutor" |

## How Unlearn differs from Atrium

Atrium won FalkorDB's own "Memory Meets Motion" hackathon ([FalkorDB's recap](https://www.falkordb.com/blog/memory-meets-motion-the-falkordb-standouts/)) by grouping students by misconception. Unlearn keeps that grouping (`cohorts`, WCC over shared misconceptions) and adds what a grouping can't tell a teacher:
- **Why.** `root_cause` traverses prerequisites to the skill that broke, often in another topic.
- **Memory across sessions.** Session 2 opens with what session 1 found.
- **Multi-agent handoff through the graph.** Tasks are claimed, handed off and approved, all as graph state.
- **A human approval gate.** Nothing the agents propose takes effect until a teacher approves it.
- **An MCP server** over the same fixed tools.
- **A measured eval** against vector RAG and no memory.

## How Unlearn maps to the tracks

Each row is a track's official key-focus item. "Partial" means some of it is met, and the row says what is missing. Query names are in [`api/unlearn/queries.py`](../api/unlearn/queries.py).

**Track 02: Agent Memory and Coordination (primary)**

| Key focus | Met? | What Unlearn does | Proof |
| --- | --- | --- | --- |
| episodic, semantic and procedural memory | Partial | **Episodic:** every answer is an `ATTEMPTED` edge, and each session is a `Session` with `Event`s (attempt, explanation, diagnosis, remediation). **Semantic:** `SHOWED {count, confidence}` and `MASTERED`. **Procedural:** `Skill → Step` with a `success_rate` that every check answer updates, and the Tutor picks the best-rated skill. Partial because the procedures themselves don't change: the 8 skills and their steps are authored (`data/curated/skills.json`). Unlearn learns *which* skill works, never new steps. | `RECORD_ATTEMPT`, `START_SESSION`, `LOG_EVENT`; `UPDATE_SHOWED`, `MARK_MASTERED`; `PICK_SKILL`, `UPDATE_SKILL` |
| persistent conversation history | Partial | What happened in each session persists in the graph across restarts: answers, explanations, the diagnosis and the remediation result. Session 2 opens from it. Partial because the wording isn't kept: the agents' messages aren't stored, so there is no transcript, and the teacher chat answers each message without the earlier turns. | `STUDENT_SESSIONS`, `RECALL`, `SESSION_ATTEMPTS`; `agents/teacher_chat.py` (one turn per call) |
| shared state and handoffs between agents | Yes | Diagnoser, Tutor and Teacher coordinate only through graph state. A `Task` is claimed atomically, completed, and handed off (`HANDED_OFF_FROM`). The Teacher's `Proposal` waits for a human. Each HTTP step reads its state back from the graph; the agents keep none in Python. | `CREATE_TASK`, `CLAIM`, `CLAIM_TASK`, `HANDOFF`, `CHAIN`, `PROPOSE`, `DECIDE`; `tests/test_claim_race.py` |
| high-concurrency reads and writes | Partial | Ten class graphs with 30 students each, 300 sessions at once: 11,892 queries/s, p50 about 25 ms and p95 35–43 ms per class, 0 errors. With two classes, heavy writes on one class barely move another class's p50 (0.33 → 0.57 ms). Partial because it was all measured on one laptop. Writes within one class graph queue behind each other (p50 294 ms under heavy writes on the same class), and the server's shared threads raise another class's p95 (0.38 → 28 ms). | `eval/concurrency.py`, [`eval/results/concurrency.json`](../eval/results/concurrency.json), `CONC_PROBE_WRITE`, `CONC_HEAVY_WRITE` |
| separate memory per user or tenant | Yes | Each classroom (tenant) is its own graph, copied from `class_template` with `GRAPH.COPY`. Each student's memory is their own `SHOWED`, `MASTERED`, `ATTEMPTED` and `Session` edges inside it. There are no logins, so separation is by graph, not by access control. | `db.recreate_graph` (`GRAPH.COPY`), `scripts/05_new_class.py`, `tools.graph_name` |

**Track 01: Agents That Act on Connected Data (secondary)**

| Key focus | Met? | What Unlearn does | Proof |
| --- | --- | --- | --- |
| multi-hop reasoning | Yes | `root_cause` walks up to 4 `REQUIRES` hops below the target and weighs misconception evidence on each prerequisite. The chain shown on screen is the shortest path to the winner. The Diagnoser descends the prerequisites level by level. | `ROOT_CAUSE`, `ROOT_CAUSE_CHAIN`, `PROBE_FRONTIER`, `LEARNING_PATH`, `LEARNING_PATH_SP` (`algo.SPpaths`) |
| graph queries and algorithms as agent tools | Yes | 16 fixed tools in `api/unlearn/tools.py`. The agents call them and nothing else. The Teacher uses WCC (cohorts), PageRank (keystones) and betweenness (bridges). The Tutor uses shortest paths. `diagnose_text` uses the vector index. | `COHORTS_WCC` (`algo.WCC`), `KEYSTONES` (`algo.pageRank`), `BRIDGES` (`algo.betweenness`), `LEARNING_PATH_SP`, `DIAGNOSE_TEXT` (`db.idx.vector.queryNodes`) |
| tool selection through MCP | Partial | `api/unlearn/unlearn_mcp.py` exposes 7 of the tools (no approve, no Cypher) to MCP clients. Checked over stdio and listed in MCP Inspector. Inside the app, the teacher chat lets an LLM choose among the same 7 tools by function calling, not MCP. Measured in-app: on 30 dev and 10 held-out teacher questions, the local model called exactly the expected tools for 30/30 and 10/10 (`eval/tool_routing.py`). Partial because no LLM client has yet been tested choosing tools over MCP (Claude Desktop wasn't tested); the benchmark uses function calling inside the app. The Diagnoser and Tutor call tools in fixed code, not by LLM choice. | `api/unlearn/unlearn_mcp.py`, `tests/test_mcp.py`, [`docs/mcp.md`](mcp.md); `agents/teacher_chat.py` |
| actions based on what the graph shows | Yes | The Diagnoser picks each next question from what the graph has ruled out. The Tutor picks the skill with the best `success_rate`. The Teacher proposes a regroup from a cohort, or practice on a student's root cause; the teacher chat can also propose a skip-ahead. An approved proposal is applied from the graph's own edges and logged as an `Event`. | `NEXT_QUESTION`, `PICK_SKILL`, `PROPOSE`, `DECIDE`, `EXEC_REGROUP`, `EXEC_SKIP_AHEAD`, `EXEC_ASSIGN_PRACTICE`, `LOG_PROPOSAL_EVENT` |
| explainable results | Yes | Every tool call returns a receipt: the query name, its parameters and the rows. The UI shows the Cypher behind each claim. An LLM reply that names anything not in that turn's rows is rejected, retried once, and then replaced by a template built from the rows. | `tools._Receipt`, `llm.check_reply`; the Receipts panel in the web UI |

## Data, licences and what is synthetic

| Source | What | Status | Licence |
| --- | --- | --- | --- |
| [Eedi Misconceptions Graph v1.0](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph), pinned to commit `2ae0839debf73c0ce7dd6578d8ea8b99e7be8631` | 2,258 constructs (Subject → Topic → SubTopic hierarchy), 8,117 misconceptions, 19,294 weighted misconception↔construct edges | Real | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `data/curated/requires.csv` | 57 prerequisite edges between 40 constructs (10 of 57 marked medium or low confidence) | Authored (AI draft, human review: 2 edges deleted, see [REVIEW.md](../REVIEW.md)) | MIT (this repo) |
| `data/curated/questions.json` | 120 multiple-choice questions, each wrong option tied to an Eedi misconception, maths checked with `fractions.Fraction` | Authored (AI draft, human review: 9 options removed, see [REVIEW.md](../REVIEW.md)) | MIT |
| `data/curated/skills.json` | 8 remediation skills | Authored (AI draft, human review) | MIT |
| Students, attempts, sessions | 30 simulated students in `class_demo`, Asha and Ben in `class_demo_video` | Synthetic | MIT |

**Attribution** (required by the licence):

> "[Eedi Misconceptions Graph v1.0](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph)" by Eedi, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Adapted: filtered to Number/Fractions for the class graphs, with curated prerequisite edges and generated questions added.

Eedi does not endorse this project. There are no real students, logins or personal data anywhere.
