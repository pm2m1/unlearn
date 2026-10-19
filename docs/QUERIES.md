# Every query

[Back to the README](../README.md)

<!-- queries:start -->
126 queries, all parameterised, all in [`api/unlearn/queries.py`](../api/unlearn/queries.py).

**Agent tools (the 16 tools and the queries they run)**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `RECORD_ATTEMPT` | `record_attempt`: store an answer and return the misconception behind the chosen option | MATCH + CREATE edge |
| `UPDATE_SHOWED` | `record_attempt`: semantic memory, confidence 1 − 0.5^count | MERGE ON CREATE / ON MATCH |
| `MASTERY_EVIDENCE` | `record_attempt`: correct answers and the strongest misconception on a construct | aggregation |
| `MARK_MASTERED` | `record_attempt`: mark MASTERED when earned | MERGE |
| `DIAGNOSE_TEXT` | `diagnose_text`: free-text explanation to this construct's misconceptions | vector index (`db.idx.vector.queryNodes`) + traversal filter |
| `NEXT_QUESTION` | `next_question`: a question not asked this session, fresh first, probing unshown misconceptions (never a pilot check item) | pattern predicates (`NOT (s)-[:ATTEMPTED {session}]->(q)`) |
| `QUESTION_OPTIONS` | `next_question`: the question's options | traversal |
| `ROOT_CAUSE` | `root_cause`: unmastered prerequisites ranked by weighted misconception evidence, deeper wins ties | variable-length `REQUIRES*1..4`, aggregation |
| `ROOT_CAUSE_CHAIN` | `root_cause`: the REQUIRES chain from target to root cause, for the receipt | variable-length path |
| `PROBE_FRONTIER` | `probe_frontier`: deepest unmastered, unprobed prerequisites | variable-length path + pattern predicates |
| `LEARNING_PATH` | `learning_path`: teaching order, deepest first | variable-length `REQUIRES*0..6` |
| `LEARNING_PATH_SP` | `learning_path`: shortest chain to one construct | `algo.SPpaths` |
| `RECALL` | `recall`: misconceptions shown, those on the last diagnosed root first, with their latest events | episodic + semantic traversal |
| `PICK_SKILL` | `pick_skill`: best remediation skill for a misconception | procedural memory |
| `SKILL_STEPS` | `pick_skill`: the skill's ordered steps | traversal |
| `UPDATE_SKILL` | `update_skill`: success rate with a +2/+3 prior | two ordered SETs |
| `SKILL_BY_NAME` | `update_skill`: read the updated skill back | index lookup |
| `COHORTS_CLEAR` | `cohorts`: drop the old gap-sharing edges | DELETE |
| `COHORTS_LINK` | `cohorts`: link students who share a confident misconception | pattern match + CREATE |
| `COHORTS_WCC` | `cohorts`: group students into cohorts | `algo.WCC` |
| `KEYSTONES` | `keystones`: constructs most of the topic depends on | `algo.pageRank` |
| `SET_PAGERANK` | `keystones`: write scores back | UNWIND + SET |
| `BRIDGES` | `bridges`: constructs where misconceptions cross topics (curriculum graph) | `algo.betweenness` (fixed seed) |
| `CLAIM` | `claim`: oldest submitted task for an agent; exactly one worker wins | per-graph write serialisation |
| `HANDOFF` | `handoff`: close a task, open the next, keep the chain and its context | CREATE + SET in one write |
| `PROPOSE` | `propose`: a pending Proposal for the teacher | CREATE + UNWIND |
| `SUPERSEDE_REGROUPS` | `propose` (regroup): supersede pending regroups whose students it contains | list predicate `all()` |
| `DECIDE` | `decide`: approve or reject a pending proposal | conditional MATCH + SET |

**Approval executor (runs only after `decide(approved)`)**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `EXEC_REGROUP` | regroup: `(:Group)-[:HAS_MEMBER]->(:Student)` for the proposal's FOR students | MERGE |
| `EXEC_SKIP_AHEAD` | skip_ahead: MASTERED {evidence:'teacher_override'}, never over an earned one | MERGE ON CREATE |
| `EXEC_ASSIGN_PRACTICE` | assign_practice: `(:Assignment)-[:FOR]->(:Student)`, `-[:PRACTICES]->(:Construct)` | CREATE |
| `LOG_PROPOSAL_EVENT` | log the applied change as an Event on the Proposal | CREATE + FOREACH/CASE |

**Sessions, tasks and steppable agents**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `START_SESSION` | open a Session (n = previous sessions + 1) | aggregation + CREATE |
| `LOG_EVENT` | episodic memory: an Event ABOUT a misconception and/or construct | CREATE + FOREACH/CASE |
| `CREATE_TASK` | the first task of a chain, with its construct and session | CREATE |
| `TASK_CONTEXT` | a task's student, construct, session and pending question | traversal |
| `TASK_STATE` | a task's state (claim-race test) | index lookup |
| `COMPLETE_TASK` | end a chain without handing off | SET |
| `FAIL_TASK` | mark a task failed so the session ends | SET |
| `CLAIM_TASK` | claim one specific task (an HTTP request driving its own session) | per-graph write serialisation |
| `CLAIM_IN_SESSION` | CLAIM limited to one session (simulated sessions) | per-graph write serialisation |
| `OPEN_TASKS_FOR` | read-only check before the API's Teacher worker claims | GRAPH.RO_QUERY |
| `SET_PENDING` | the question a task is waiting on | SET |
| `SET_TUTOR_PLAN` | what the Tutor taught, for the check answer's request | SET |
| `SESSION_TASKS` | a session's tasks (routes an HTTP answer) | property match |
| `SESSION_ATTEMPTS` | this session's answers in order: the Diagnoser's search state | edge property filter |
| `SESSION_RULED_OUT` | constructs answered right this session plus everything they depend on | variable-length `REQUIRES*0..6` |
| `SESSION_LOOKUP` | which student a session belongs to | traversal |
| `STUDENT_SESSIONS` | a student's sessions | traversal |
| `SESSION_SCORE` | correct / answered in one session | aggregation |
| `CHAIN` | every task handed off from a root task | variable-length `HANDED_OFF_FROM*0..` |
| `CHAIN_OPEN` | open tasks in a chain (session end) | variable-length path |
| `SHOWED_ON` | a student's misconceptions on one construct, by weighted evidence | traversal + SEEN_IN.w |
| `STUDENT_SHOWED` | all of a student's SHOWED edges | traversal |
| `NAME_VOCABULARY` | every construct and misconception name, for the LLM receipt check | label scan |
| `PROPOSALS` | proposals by state, with their students | aggregation |
| `PROPOSAL_LOOKUP` | find a proposal's class graph | property match |

**UI, API and demo reads**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `SLICE_FOR_TARGET` | graph panel: the constructs under a target | variable-length `REQUIRES*0..6` |
| `SLICE_EDGES` | graph panel: REQUIRES edges among them | variable-length path |
| `STUDENT_SHOWED_ON_SLICE` | graph panel: the student's misconceptions on the slice | traversal + IN list |
| `STUDENT_MASTERED_ON_SLICE` | graph panel: mastered constructs | traversal + IN list |
| `CLASS_STUDENTS` | students with their session counts | aggregation |
| `TARGETS` | constructs with prerequisites, deepest chains first (topic picker) | variable-length path + aggregation |
| `QUIZ_SCORES` | fractions-check scores (demo scenario) | edge property filter + aggregation |
| `LOAD_STUDENT_PROFILES` | demo scenario students and their planted simulator profile | UNWIND + MERGE |
| `STUDENT_SIM_PROFILE` | read a scenario student's profile (simulated answers only) | index lookup |
| `COUNT_NODES` | /health node counts | aggregation |
| `RESET_STUDENT_SESSIONS` | demo reset: a student's sessions and events | DETACH DELETE |
| `RESET_STUDENT_EDGES` | demo reset: attempts, evidence, mastery, gap links | multi-type edge match |
| `RESET_STUDENT_TASKS` | demo reset: the student's tasks | DETACH DELETE |
| `RESET_STUDENT_PROPOSALS` | demo reset: proposals, their events and assignments | DETACH DELETE |
| `RESET_STUDENT_GROUPS` | demo reset: group membership | DELETE |

**Pilot classes (`unlearn/pilot/engine.py`)**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `PILOT_DROP_UNKEPT_OPTIONS` | cut a copy of class_template down to the approved questions: their options | list predicate + DETACH DELETE |
| `PILOT_DROP_UNKEPT_QUESTIONS` | the same, the questions themselves | list predicate + DETACH DELETE |
| `PILOT_SET_QUESTION` | the pilot's wording, and `check_only` on fixed check items | SET (null removes) |
| `PILOT_CLEAR_OPTIONS` | drop a question's options before loading the pilot's | DETACH DELETE |
| `PILOT_OPTION_TAGS` | every option and its misconception, checked against the approved items | traversal |
| `PILOT_PREREQ_COUNTS` | pick the diagnosis target: the wrong check construct with the most prerequisites | variable-length `REQUIRES*1..6`, aggregation |
| `PILOT_DIAGNOSES` | a student's diagnosed roots (teacher view, session 2's recall) | episodic traversal |
| `PILOT_TUTOR_PLANS` | the skill the Tutor chose (teacher view) | traversal |

**Eval and concurrency**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `NEAREST_MISCONCEPTIONS` | the baselines' candidate retriever and the eval judge | vector index |
| `ALL_REQUIRES` | condition B+: every curated REQUIRES edge, as text in the prompt | pattern match |
| `ALL_SEEN_IN` | condition B+: every construct's misconceptions with SEEN_IN.w, as text in the prompt | pattern match |
| `CLASS_CONSTRUCTS` | the eval judge's construct names | label scan |
| `RECALL_SPEC_RULE` | design check: the build spec's recall rule (seen twice, newest first) | pattern match |
| `RECALL_STRONGEST_FIRST` | design check: recall seen once or more, strongest first | pattern match |
| `MISCONCEPTION_NAMES` | design check: planted misconception names | range index lookup |
| `CONC_PROBE_WRITE` | a small timed write (isolation probes) | MERGE |
| `CONC_HEAVY_WRITE` | a deliberately heavy write that holds a graph's write lock | UNWIND + CREATE |
| `EVAL_GRAPH_NODES` | eval provenance: every node of the graph an eval read, for its fingerprint | label scan, `properties()` |
| `EVAL_GRAPH_EDGES` | eval provenance: every edge, with its endpoints, for the fingerprint | pattern match, `properties()` |
| `EVAL_GRAPH_INDEXES` | eval provenance: every index and its options (the vector index's efRuntime), for the fingerprint | `db.indexes()` |

**Loading and indexes**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `CURRICULUM_INDEXES` | range indexes on Subject/Topic/SubTopic/Construct/Misconception ids | range index |
| `CLASS_INDEXES` | plus Question, Student, Task.state and the 384-d cosine vector index (efRuntime 1000: exact search) | range + vector index |
| `LOAD_HIERARCHY` | Subject → Topic → SubTopic → Construct from construct-map.csv | UNWIND + MERGE (batches of 500) |
| `LOAD_MISCONCEPTIONS` | misconceptions and weighted SEEN_IN edges | UNWIND + MERGE |
| `LOAD_SHARES_MISCONCEPTION` | derived SHARES_MISCONCEPTION edges (curriculum graph) | UNWIND + MERGE |
| `SLICE_CONSTRUCTS` | the class slice read out of `curriculum` | traversal + IN list |
| `SLICE_SEEN_IN` | the slice's misconceptions and SEEN_IN edges | traversal |
| `SET_SEEN_IN_WEIGHTS` | SEEN_IN.w: the misconception's share of its weight within the slice | aggregation + SET |
| `LOAD_REQUIRES` | curated REQUIRES edges | UNWIND + MERGE |
| `LOAD_QUESTIONS` | questions ASSESSES constructs | UNWIND + MERGE |
| `LOAD_OPTIONS` | options, and INDICATES for wrong ones | UNWIND + FOREACH/CASE |
| `LOAD_SKILLS` | remediation skills | UNWIND + MERGE |
| `LOAD_SKILL_STEPS` | ordered skill steps | UNWIND + CREATE |
| `LOAD_REMEDIATES` | skill → misconception | UNWIND + MERGE |
| `LOAD_AGENTS` | Diagnoser, Tutor, Teacher | UNWIND + MERGE |
| `LOAD_EMBEDDINGS` | misconception embeddings | `vecf32` |
| `LOAD_STUDENTS` | synthetic students | UNWIND + MERGE |

**Checks used by the loaders and tests**

| Query | Purpose | FalkorDB feature |
| --- | --- | --- |
| `COUNT_NODES_BY_LABEL` | node counts per label | aggregation |
| `COUNT_EDGES_BY_TYPE` | edge counts per type | aggregation |
| `COUNT_SEEN_IN` | SEEN_IN count (19,294 expected) | aggregation |
| `COUNT_HIERARCHY_EDGES` | hierarchy edge counts | aggregation |
| `COUNT_SHARES_MISCONCEPTION` | derived edge count | aggregation |
| `ASYMMETRIC_SHARES_MISCONCEPTION` | every derived edge has its reverse | pattern predicate |
| `SEEN_IN_PCT_SUMS` | each misconception's pct sums to 100 | aggregation |
| `LIST_INDEXES` | indexes survive GRAPH.COPY | `db.indexes()` |
| `COUNT_EMBEDDED` | every misconception has a vector | aggregation |
| `REQUIRES_MAX_DEPTH` | longest REQUIRES chain | variable-length path |
| `REQUIRES_PROPS` | REQUIRES edges carry source and weight | aggregation |
| `SHOWED_ON_WEIGHTS` | SEEN_IN pct and w for one misconception | traversal |
| `GROUP_MEMBERS` | approval test read-back | traversal |
| `ASSIGNMENTS_FOR` | approval test read-back | traversal |
| `MASTERED_EDGE` | approval test read-back | traversal |
| `PROPOSAL_EVENTS` | approval test read-back | traversal |
| `COUNT_LABELS` | rejection changes nothing | aggregation |
<!-- queries:end -->
