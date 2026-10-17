# Unlearn — Build Spec (Graph Hacks)

Oct 17, 2026 · Parth

## TL;DR

Unlearn is a tutor agent that works out *which* misconception a student holds, traces it back to the prerequisite that actually broke, and remembers it next session. Each classroom gets its own FalkorDB graph, and three agents (Diagnoser, Tutor, Teacher) hand work to each other through it.

- **Pitch:** two students both score 40% on fractions and need opposite fixes. A chat tutor can't tell them apart. Unlearn can, and shows the graph path that proves it.
- **Tracks:** 02 Agent Memory and Coordination (primary), 01 Agents That Act on Connected Data (secondary).
- **Deadline:** submit by Oct 18, 22:00 IST (2-hour buffer before the 23:59 close).
- **Remove-FalkorDB test:** without the graph there is no misconception-to-concept grounding, no prerequisite root-cause traversal, no per-class memory, no agent handoffs and no cohort grouping. It collapses into generic chat. Put this line at the top of the README.
- **Prior art to beat:** Atrium won FalkorDB's own "Memory Meets Motion" hackathon by grouping students by misconception. Unlearn adds root-cause traversal, cross-session memory, multi-agent handoff, an MCP server and a measured eval. Name Atrium in the README.

## Scope and non-goals

One subject (Maths), one topic cluster (Fractions, about 30–40 constructs), one classroom demo with 30 simulated students. Everything else is a non-goal.

**Topic options.** Pick one; Fractions is the default. Building more than one in 40 hours would cost you the eval. Confirm the topic names with `TopicName.value_counts()` before committing.

| Topic | Prerequisite chain | Verdict |
| --- | --- | --- |
| Fractions (default) | place value, division, multiples/LCM → equivalent fractions → adding and subtracting → simplifying | Safe choice. Deep chains, text-only questions |
| Solving linear equations | negative numbers → order of operations → collecting like terms → expanding brackets → solving | Best alternative. Very relatable, text-only questions, and the root cause often sits in a different topic (negative numbers) |
| Algebraic fractions | number fractions → factorising → expanding → algebraic fractions | Best demo moment: a student fails algebra because of Year 6 fractions, 3–4 hops back. About twice the authoring, since you build the fractions layer too |
| Percentages | fractions/decimals → percentages → percentage change → reverse percentages | Good. Relatable through discounts and marks, but shorter chains |

**In scope**

- Full Eedi construct and misconception graph loaded (cheap, and it shows scale)
- Hand-curated prerequisite edges for the chosen topic only
- 3–5 multiple-choice questions per construct in the chosen topic, each wrong option tied to a misconception
- Three agents, sixteen graph tools, one approval gate
- MCP server exposing the same tools
- Eval: graph vs vector RAG vs no memory
- One deployed URL plus Docker Compose for local setup

**Out of scope**

- Real students, logins or personal data (the rules forbid personal data)
- Other subjects or topics
- Cross-classroom analytics
- LLM-written Cypher on the main path
- Mobile layout polish

## Architecture

Five layers, and only the tools layer touches the database. Agents never write Cypher, and the LLM never states a fact that didn't come back in a tool's rows.

```
 Student UI        Teacher dashboard        Claude Desktop / Cursor
     |                    |                          |
     +---------+----------+                          |
               v                                     v
   FastAPI: sessions, answers, approvals         MCP server
               |                                     |
               +------------------+------------------+
                                  v
   +--------------------------------------------------------------+
   | Agents (asyncio workers that claim Tasks from the graph)     |
   |   Diagnoser --handoff--> Tutor --handoff--> Teacher agent    |
   |   LLM chain: Groq, Gemini, OpenRouter, then template.        |
   |   Writes words, never facts.                                 |
   +--------------------------------------------------------------+
                                  v
   +--------------------------------------------------------------+
   | 16 fixed Cypher tools (queries.py)                           |
   | Each returns rows plus a receipt: query, params, node ids    |
   +--------------------------------------------------------------+
                                  v
   +--------------------------------------------------------------+
   | FalkorDB: one instance, one graph per classroom              |
   |   curriculum --filter--> class_template --GRAPH.COPY--> class_<id> |
   +--------------------------------------------------------------+
                                  ^
   Seed scripts: Eedi CSVs plus curated prerequisites, questions and skills
```

Requests flow down from the UIs or an MCP client to the agents, which reason through the 16 tools against one class graph. Each class graph is a `GRAPH.COPY` of the template, which is itself a filtered slice of the Eedi curriculum plus your curated files.

## Data sources

One real dataset (Eedi, CC BY 4.0) supplies the misconception graph. Everything else is authored or synthetic, and the README must say so.

| Source | What you get | Status | Licence |
| --- | --- | --- | --- |
| [Eedi Misconceptions Graph v1.0](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph) `data/construct-map.csv` | 2,258 constructs with Subject → Topic → SubTopic hierarchy | Real | CC BY 4.0 |
| Same dataset, `data/misconception-map.csv` | 19,294 weighted misconception↔construct edges, 8,117 misconceptions | Real | CC BY 4.0 |
| `REQUIRES` prerequisite edges | Construct → prerequisite construct, chosen topic only | Authored by you (LLM draft + manual review) | Yours |
| Questions and options | 3–5 MCQs per construct, each wrong option → one misconception | Generated + reviewed | Yours |
| Students and attempts | 30 simulated students with planted misconceptions | Synthetic | Yours |

**Exact columns** (from the dataset's data dictionary):

- `misconception-map.csv`: `MisconceptionId`, `MisconceptionName`, `PercentageMisconceptionExistsInThisConstruct`, `ConstructId`, `ConstructName`, `SubTopicSubjectId`, `SubTopicName`, `TopicSubjectId`, `TopicName`, `SubjectSubjectId`, `SubjectName`
- `construct-map.csv`: `SubjectName`, `SubjectSubjectId`, `TopicName`, `TopicSubjectId`, `SubTopicName`, `SubTopicSubjectId`, `ConstructName`, `ConstructId`
- Join on `ConstructId`. Edge weights for one `MisconceptionId` sum to 100.
- The 4 subjects are Number, Geometry and Measure, Algebra, Data and Statistics. Fractions sits under Number.

**Facts that shape the design**

- The release has no questions, no distractors and no student data. You must generate questions yourself.
- There are no construct-to-construct prerequisite edges. `REQUIRES` is your own work, so label it `source:'curated'`.
- Download from the canonical `Eedi/Eedi-Misconceptions-Graph` repo (public), pinned to commit `2ae0839debf73c0ce7dd6578d8ea8b99e7be8631`. The duplicate `wangwangduishuidajiao/Eedi-Misconceptions-Graph` is only a fallback.
- Do not commit the Kaggle "Mining Misconceptions" CSVs. Their redistribution terms are unverified.

**Attribution line for the README** (required by the licence):

> "Eedi Misconceptions Graph v1.0" by Eedi, licensed under CC BY 4.0. Adapted: filtered to Number/Fractions for the class graphs, with curated prerequisite edges and generated questions added.

Do not imply Eedi endorses the project.

## Graph data model

Three kinds of graph live in one FalkorDB instance: a read-only `curriculum`, a `class_template`, and one `class_<id>` per classroom cloned from the template with `GRAPH.COPY`. FalkorDB serialises writes per graph, so classrooms never block each other's writes. That is your Track 02 "high-concurrency" argument.

| Graph | Contents | Written by |
| --- | --- | --- |
| `curriculum` | Full Eedi hierarchy, all 8,117 misconceptions, derived `SHARES_MISCONCEPTION` edges | Loader, once |
| `class_template` | Topic subgraph, `REQUIRES` edges, questions, options, remediation skills, indexes | Loader, once |
| `class_<id>` | Copy of the template plus students, sessions, events, tasks, proposals | Agents, live |

**Schema**

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
(:Task {id,kind,state,claimed_by,created_ts,construct_id,session})-[:ABOUT]->(:Student)   // construct and session: the task's context
(:Task)-[:ASSIGNED_TO]->(:Agent)
(:Task)-[:HANDED_OFF_FROM]->(:Task)
(:Proposal {id,kind,state,payload})-[:FOR]->(:Student)                  // waits for teacher approval
(:Proposal)-[:HAD_EVENT]->(:Event)                                     // logged when an approval is applied
(:Group {id})-[:HAS_MEMBER]->(:Student)                                // applied regroup
(:Assignment {id,ts,proposal})-[:FOR]->(:Student), (:Assignment)-[:PRACTICES]->(:Construct)   // applied assign_practice
(:Student)-[:SHARES_GAP {miscs}]->(:Student)                            // derived for cohorts
```

**Edge direction rule:** `REQUIRES` always points from the harder construct to its prerequisite. PageRank scores incoming edges, so foundational constructs rank highest. Never mix directions.

**How Track 02's memory types map**

| Memory type | Where it lives | Example |
| --- | --- | --- |
| Episodic | `Session`, `Event`, `ATTEMPTED` | "On Oct 17 Asha picked B on Q12" |
| Semantic | `SHOWED`, `MASTERED` | "Asha adds numerators and denominators" |
| Procedural | `Skill` → `Step`, with `success_rate` | "Fraction-wall play worked 3 of 4 times" |
| Shared state | `Task`, `Proposal` | "Diagnoser handed Asha to Tutor" |

**Indexes** (create on `curriculum` and `class_template`; `GRAPH.COPY` carries indexes to every class graph)

```
CREATE INDEX FOR (c:Construct) ON (c.id)
CREATE INDEX FOR (m:Misconception) ON (m.id)
CREATE INDEX FOR (q:Question) ON (q.id)
CREATE INDEX FOR (s:Student) ON (s.id)
CREATE INDEX FOR (t:Task) ON (t.state)
CREATE VECTOR INDEX FOR (m:Misconception) ON (m.embedding) OPTIONS {dimension:384, similarityFunction:'cosine'}
```

Use a 384-dimension local embedding model: `all-MiniLM-L6-v2`, run through fastembed (ONNX Runtime, no torch). It runs on CPU, costs nothing and has no rate limit. Its vectors match the sentence-transformers ones to cosine ≥ 0.9999998, and it keeps the API image at ~0.9 GB instead of ~2.2 GB.

## Data loading pipeline

Five idempotent scripts, run in order by `make seed`. Each one batches rows with `UNWIND $rows` (500 per batch) and creates indexes before any `MERGE`.

1. `01_download.py` pulls both CSVs into `data/raw/` with `huggingface_hub.hf_hub_download` and records the commit hash.
2. `02_load_curriculum.py` loads the hierarchy and misconceptions into `curriculum`.
3. `03_derive.py` computes `SHARES_MISCONCEPTION` in pandas and writes it.
4. `04_build_template.py` builds `class_template`: topic subgraph, curated `REQUIRES`, questions, skills, embeddings, indexes.
5. `05_new_class.py --id demo --students 30` copies the template to `class_demo` and seeds simulated students.

**Hierarchy load**

```
UNWIND $rows AS r
MERGE (s:Subject {id:r.subject_id}) ON CREATE SET s.name = r.subject
MERGE (t:Topic {id:r.topic_id}) ON CREATE SET t.name = r.topic
MERGE (st:SubTopic {id:r.subtopic_id}) ON CREATE SET st.name = r.subtopic
MERGE (c:Construct {id:r.construct_id}) ON CREATE SET c.name = r.construct
MERGE (s)-[:HAS_TOPIC]->(t)
MERGE (t)-[:HAS_SUBTOPIC]->(st)
MERGE (st)-[:HAS_CONSTRUCT]->(c)
```

**Misconception load**

```
UNWIND $rows AS r
MERGE (m:Misconception {id:r.mid}) ON CREATE SET m.name = r.mname
WITH m, r
MATCH (c:Construct {id:r.cid})
MERGE (m)-[e:SEEN_IN]->(c) ON CREATE SET e.pct = r.pct
```

**Deriving `SHARES_MISCONCEPTION`.** Do the self-join in pandas, not Cypher. A misconception spread across many constructs creates tens of thousands of pairs. Keep pairs with `n >= 2` shared misconceptions and write both directions, because FalkorDB algorithms follow edge direction.

**Picking the topic slice**

- Run `df[df.SubjectName == 'Number'].TopicName.value_counts()` first. Topic names below are what to look for, not verified values.
- Take the fractions topic (likely named "Fractions"). If it has more than 60 constructs, keep 2–3 SubTopics, for example equivalent fractions, adding/subtracting, and simplifying.
- Add 5–8 prerequisite constructs from outside it (multiples/LCM, factors/HCF, place value, division). Root causes that cross topics are the strongest demo moment.
- Copy into the template every misconception with a `SEEN_IN` edge to a kept construct.

**Curated prerequisites** live in `data/curated/requires.csv` with columns `construct_id,prereq_id,note`.

1. Ask an LLM to draft edges from the construct names only.
2. Review every row by hand (about 45 minutes for 40–60 rows). Delete anything you can't justify in one sentence.
3. Check it is acyclic with `networkx.is_directed_acyclic_graph` before loading. Fail the script if not.
4. Set `weight: 1` on every `REQUIRES` edge (needed by `algo.SPpaths`).

**Questions** live in `data/curated/questions.json`:

```
{"id":"q-fr-012","construct_id":1234,"text":"1/3 + 1/4 = ?",
 "options":[{"key":"A","text":"7/12","correct":true},
            {"key":"B","text":"2/7","misconception_id":12345},
            {"key":"C","text":"1/7","misconception_id":12346},
            {"key":"D","text":"2/12","misconception_id":12347}]}
```

Each wrong option must map to a misconception that has a `SEEN_IN` edge to the question's construct. The loader rejects any that don't.

**Embeddings.** Encode only the template's misconception names (a few hundred), then:

```
UNWIND $rows AS r
MATCH (m:Misconception {id:r.id})
SET m.embedding = vecf32(r.v)
```

**Skills.** Write 6–8 remediation plays by hand (fraction wall, number line, area model, LCM-first common denominators, worked-example contrast, estimation check). Link each with `REMEDIATES` to the misconceptions it fits. Start every `success_rate` at 0.5.

## Agent tools

Sixteen fixed, parameterised Cypher tools do all the reasoning. The LLM only picks tools and writes the reply. Every tool returns `{cypher, params, rows, node_ids}` so the UI can draw a path receipt.

| Tool | Used by | Kind | FalkorDB feature |
| --- | --- | --- | --- |
| `record_attempt` | Diagnoser | write | MERGE on edges |
| `diagnose_text` | Diagnoser | read | vector index + traversal |
| `next_question` | Diagnoser | read | pattern predicates |
| `root_cause` | Tutor | read | variable-length `REQUIRES*1..4` |
| `probe_frontier` | Diagnoser | read | variable-length traversal |
| `learning_path` | Tutor | read | `algo.SPpaths` + traversal |
| `recall` | Tutor | read | episodic + semantic memory |
| `pick_skill` / `update_skill` | Tutor | read/write | procedural memory |
| `cohorts` | Teacher | write + read | `algo.WCC` |
| `keystones` / `bridges` | Teacher | read | `algo.pageRank`, `algo.betweenness` |
| `handoff` / `claim` / `propose` / `decide` | All | write | per-graph write serialisation |

### Diagnosis

**`record_attempt`** runs two queries. First it records the answer and returns the misconception behind the chosen option:

```
MATCH (s:Student {id:$sid}), (q:Question {id:$qid})
MATCH (o:Option {qid:$qid, key:$key})
CREATE (s)-[a:ATTEMPTED {ts:$ts, session:$sess, option:$key, correct:o.correct}]->(q)
WITH o
OPTIONAL MATCH (o)-[:INDICATES]->(m:Misconception)
RETURN o.correct AS correct, m.id AS mid, m.name AS misconception
```

If `mid` is not null, it updates semantic memory. Confidence is 1 − 0.5^count, so one hit gives 0.5 and three give 0.875:

```
MATCH (s:Student {id:$sid}), (m:Misconception {id:$mid})
MERGE (s)-[e:SHOWED]->(m)
ON CREATE SET e.count = 1, e.confidence = 0.5, e.first_ts = $ts, e.last_ts = $ts
ON MATCH SET e.count = e.count + 1, e.confidence = 1 - 0.5 ^ (e.count + 1), e.last_ts = $ts
```

Mark `MASTERED` in Python: two correct answers on a construct's questions and no `SHOWED` above 0.6 on that construct's misconceptions.

**`diagnose_text`** maps a student's free-text explanation to misconceptions, but only those seen in the current construct. Vector queries can't filter, so over-fetch 25 and filter with the traversal:

```
CALL db.idx.vector.queryNodes('Misconception', 'embedding', 25, vecf32($v)) YIELD node, score
MATCH (node)-[e:SEEN_IN]->(:Construct {id:$cid})
RETURN node.id AS id, node.name AS name, score, e.pct AS pct
ORDER BY score ASC LIMIT 3
```

Test on 3 known examples whether `score` is a distance (lower is closer) or a similarity, and fix the `ORDER BY` to match.

**`next_question`** picks a question on the construct that hasn't been asked in the *current* session. Never-attempted questions come first, then the least recently attempted. Ties go to the question whose wrong options probe the most misconceptions the student hasn't shown yet. Excluding only this session's attempts lets session 2 ask about the root cause again, even though there are only 3 questions per construct:

```
MATCH (s:Student {id:$sid})
MATCH (q:Question)-[:ASSESSES]->(:Construct {id:$cid})
WHERE NOT (s)-[:ATTEMPTED {session:$sess}]->(q)
OPTIONAL MATCH (s)-[a:ATTEMPTED]->(q)
WITH s, q, max(a.ts) AS last_ts
MATCH (o:Option)-[:OPTION_OF]->(q)
OPTIONAL MATCH (o)-[:INDICATES]->(m:Misconception)
OPTIONAL MATCH (s)-[e:SHOWED]->(m)
WITH q, last_ts, count(DISTINCT m) AS probes, sum(CASE WHEN m IS NOT NULL AND e IS NULL THEN 1 ELSE 0 END) AS unprobed
RETURN q.id AS id, q.text AS text, probes, unprobed, last_ts, last_ts IS NULL AS fresh
ORDER BY fresh DESC, last_ts ASC, unprobed DESC, probes DESC LIMIT 1
```

### Root cause (the hero tool)

**`root_cause`** walks up to 4 hops back through prerequisites and ranks unmastered ones by weighted misconception evidence. Deeper wins ties, because the deepest broken prerequisite is the real cause:

```
MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})
MATCH p = (c)-[:REQUIRES*1..4]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
WITH s, pre, min(length(p)) AS depth
OPTIONAL MATCH (s)-[e:SHOWED]->(m:Misconception)-[si:SEEN_IN]->(pre)
WITH pre, depth, sum(coalesce(e.count, 0) * coalesce(e.confidence, 0.0) * coalesce(si.w, 0.0)) AS evidence, collect(DISTINCT m.name) AS miscs
WHERE evidence > 0
RETURN pre.id AS id, pre.name AS name, depth, evidence, miscs
ORDER BY evidence DESC, depth DESC LIMIT 3
```

Evidence is weighted by `SEEN_IN.w`, the misconception's share of its Eedi weight within the class slice: `04_build_template.py` sets `w = pct / sum(pct over the slice's constructs for that misconception)`. A generic misconception spread over several prerequisites adds little to each. One whose Eedi weight mostly sits outside the slice is not penalised for that, which raw `pct / 100` did: it made roots with only generic misconceptions, like fraction notation (3342), nearly impossible to name. The median prerequisite distractor has `w = 1.0`, so two hits score 1.5. That is why the Diagnoser's stop thresholds are 1.5 and 0.5.

Then fetch the chain for the receipt:

```
MATCH p = (c:Construct {id:$cid})-[:REQUIRES*1..4]->(:Construct {id:$pid})
RETURN [n IN nodes(p) | n.name] AS chain, [n IN nodes(p) | n.id] AS ids
ORDER BY length(p) ASC LIMIT 1
```

**`probe_frontier`** lists the deepest unmastered prerequisites with no evidence. The Diagnoser uses it as a fallback when its top-down search (see "Agents and orchestration") has nothing left to ask:

```
MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})
MATCH p = (c)-[:REQUIRES*1..4]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
AND NOT (s)-[:ATTEMPTED]->(:Question)-[:ASSESSES]->(pre)
WITH pre, max(length(p)) AS depth
RETURN pre.id AS id, pre.name AS name, depth
ORDER BY depth DESC LIMIT 3
```

### Teaching and memory

**`learning_path`** gives the teaching order: every unmastered construct the target depends on, deepest first.

```
MATCH (s:Student {id:$sid}), (t:Construct {id:$tid})
MATCH p = (t)-[:REQUIRES*0..6]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
WITH pre, max(length(p)) AS depth
RETURN pre.id AS id, pre.name AS name, depth
ORDER BY depth DESC
```

For the shortest chain from the target down to one specific construct, use `algo.SPpaths`. `weight: 1` on every `REQUIRES` edge gives `weightProp` something to sum:

```
MATCH (t:Construct {id:$tid}), (m:Construct {id:$mid})
CALL algo.SPpaths({sourceNode: t, targetNode: m, relTypes: ['REQUIRES'], weightProp: 'weight', relDirection: 'outgoing', maxLen: 6})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.name] AS chain, pathWeight
```

**`recall`** opens each session with what the tutor remembers. It returns every misconception the student has shown, ranked:
1. those on the root cause the student was diagnosed with most recently, by their `SEEN_IN.w` there;
2. then by confidence (the most repeated);
3. then by how recently they were shown.

The original rule kept only confidence > 0.6, meaning seen twice. That left 58 of 90 simulated students with nothing to recall. The ordering was chosen after seeing the eval results: the tutor opens with what it diagnosed last session. Measured on the session-2 opening, which names the top 2:

| Rule | Recall of a planted misconception | Named misconceptions that were planted |
| --- | --- | --- |
| confidence > 0.6, newest first (original) | 28% | 78% |
| seen once or more, strongest first | 56% | 31% |
| seen once or more, last diagnosed root first (current) | 68% | 45% |

```
MATCH (s:Student {id:$sid})
OPTIONAL MATCH (s)-[:HAD_SESSION]->(:Session)-[:HAD_EVENT]->(dx:Event {type:'diagnosis'})-[:ABOUT]->(root:Construct)
WITH s, root, dx.ts AS dx_ts ORDER BY dx_ts DESC LIMIT 1
MATCH (s)-[e:SHOWED]->(m:Misconception)
WHERE e.count >= 1
OPTIONAL MATCH (m)-[si:SEEN_IN]->(root)
WITH s, m, e, coalesce(si.w, 0.0) AS on_root
OPTIONAL MATCH (s)-[:HAD_SESSION]->(:Session)-[:HAD_EVENT]->(ev:Event)-[:ABOUT]->(m)
WITH m, e, on_root, ev ORDER BY ev.ts DESC
WITH m, e, on_root, collect(ev.summary) AS events
RETURN m.name AS misconception, e.count AS times, e.confidence AS confidence, e.last_ts AS last_seen,
       on_root, events[0..3] AS recent
ORDER BY on_root DESC, confidence DESC, last_seen DESC LIMIT 5
```

**`pick_skill`** and **`update_skill`** are procedural memory. Two separate `SET` clauses keep the update order explicit:

```
MATCH (k:Skill)-[:REMEDIATES]->(:Misconception {id:$mid})
RETURN k.name AS skill, k.success_rate AS rate, k.uses AS uses
ORDER BY rate DESC LIMIT 1

MATCH (k:Skill {name:$name})
SET k.success_rate = (k.success_rate * (k.uses + 2) + $ok) / (k.uses + 3)
SET k.uses = k.uses + 1
```

The `+2` / `+3` acts as a prior, so one lucky outcome can't swing the rate to 0 or 1.

### Teacher analytics

**`cohorts`** rebuilds gap-sharing edges, then groups students with WCC:

```
MATCH ()-[g:SHARES_GAP]->() DELETE g

MATCH (a:Student)-[e1:SHOWED]->(m:Misconception)<-[e2:SHOWED]-(b:Student)
WHERE a.id < b.id AND e1.confidence > 0.6 AND e2.confidence > 0.6
WITH a, b, collect(m.name) AS miscs
CREATE (a)-[:SHARES_GAP {miscs: miscs}]->(b)

CALL algo.WCC({nodeLabels: ['Student'], relationshipTypes: ['SHARES_GAP']}) YIELD node, componentId
WITH componentId, collect(node.alias) AS students
WHERE size(students) > 1
RETURN componentId, students ORDER BY size(students) DESC
```

**`keystones`** runs PageRank on `REQUIRES` and returns the constructs most of the topic depends on. Write scores back with a separate `UNWIND` rather than `SET` after `YIELD`:

```
CALL algo.pageRank('Construct', 'REQUIRES') YIELD node, score
RETURN node.id AS id, node.name AS name, score ORDER BY score DESC LIMIT 10
```

**`bridges`** runs on the `curriculum` graph and finds constructs where misconceptions leak across topics. Fix the seed, or results change between runs:

```
CALL algo.betweenness({nodeLabels: ['Construct'], relationshipTypes: ['SHARES_MISCONCEPTION'], samplingSize: 256, samplingSeed: 42})
YIELD node, score
RETURN node.name AS name, score ORDER BY score DESC LIMIT 10
```

### Coordination

**`claim`** is safe without locks because FalkorDB runs one write at a time per graph. A second worker sees the task already `working` and gets no row:

```
MATCH (t:Task {state:'submitted'})-[:ASSIGNED_TO]->(:Agent {name:$agent})
WITH t ORDER BY t.created_ts LIMIT 1
SET t.state = 'working', t.claimed_by = $worker
RETURN t.id AS id, t.kind AS kind
```

FalkorDB's `LIMIT` does not limit eager operations that come *before* it. Here it comes first, so it should hold, but write a test that fires two claims at once and asserts exactly one wins.

**`handoff`** closes one task and opens the next, keeping the chain. The new task copies `construct_id` and `session` from `prev` in the same write, so a worker that claims it straight away never sees a task without its context:

```
MATCH (prev:Task {id:$prev}), (s:Student {id:$sid}), (a:Agent {name:$to})
CREATE (t:Task {id:$id, kind:$kind, state:'submitted', created_ts:$ts, construct_id:prev.construct_id, session:prev.session})
CREATE (t)-[:ABOUT]->(s), (t)-[:ASSIGNED_TO]->(a), (t)-[:HANDED_OFF_FROM]->(prev)
SET prev.state = 'completed'
RETURN t.id AS id
```

**`propose`** and **`decide`** are the approval gate. Nothing in a `Proposal` takes effect until the teacher approves:

```
CREATE (p:Proposal {id:$id, kind:$kind, state:'pending', payload:$json, created_ts:$ts})
WITH p UNWIND $sids AS sid
MATCH (s:Student {id:sid}) CREATE (p)-[:FOR]->(s)

MATCH (p:Proposal {id:$id, state:'pending'})
SET p.state = $decision, p.decided_ts = $ts
RETURN p.kind AS kind, p.payload AS payload
```

## Agents and orchestration

Three agents run as worker loops in plain Python (`asyncio`). Each one claims a `Task` from the graph, runs fixed tool steps, and hands off. Graph rules decide when to stop; the LLM only writes language and, in the Teacher chat, picks tools.

| Agent | Trigger | Steps | Stops when | Hands off to |
| --- | --- | --- | --- | --- |
| Diagnoser | `diagnose` task, created when a session starts | `recall` → loop: choose a construct (top-down search below) → `next_question` → `record_attempt` → `root_cause` | Top evidence ≥ 1.5 and leads the runner-up by ≥ 0.5, and the leader is the deepest suspect with nothing left to ask below it; or 6 questions asked | Tutor (`remediate`) |
| Tutor | `remediate` task | `root_cause` → `learning_path` → `pick_skill` → explain → 1 check question → `update_skill` | Check answered | Teacher (`review`) if the check answer is wrong and the root's top misconception confidence is still > 0.6, else done |
| Teacher agent | `review` tasks, or the teacher's chat | `cohorts`, `keystones`, `bridges`, `root_cause` → `propose` | Proposal written | Human teacher |

**Diagnoser search (top-down).** The Diagnoser picks which construct to ask about with a top-down search over `REQUIRES`, read through `learning_path`:
- It starts under the target and asks about the closest prerequisite not yet asked this session.
- A correct answer rules that construct out, together with everything it depends on: if you can do X, you can do what X needs.
- A wrong answer makes the construct a suspect, and the search continues below it.
- When nothing is left to ask below the deepest suspect, it asks that suspect again to confirm.
- `probe_frontier` is the fallback once the search runs dry.

On the rule-based simulator, deepest-first probing found the planted root top-1 in 8/30 students. It spent the 6-question budget on deep constructs the student already knew. The top-down search found 17–23/30.

**Tutor check question.** The Tutor asks about the root cause if it has a question left in this session. Otherwise it asks about the closest construct above the root on the `root_cause` chain, which depends on the root. `SHOWED` confidence never goes down, so a correct check answer ends the chain. A wrong one escalates only while the misconception is still held with confidence > 0.6.

**Teacher agent choice.** It proposes `regroup` when the student is in a WCC cohort (`cohorts` also returns student ids), and otherwise `assign_practice` on the student's root cause. It never proposes `skip_ahead` from a review task. That kind stays available through MCP and the teacher chat.

**Approval gate.** The Teacher agent can only create `Proposal` nodes from an allowlist: `regroup`, `skip_ahead`, `assign_practice`. `propose` checks the payload:
- `regroup` needs 2+ students;
- `skip_ahead` and `assign_practice` need an integer `construct_id`.

A human clicks approve or reject in the UI, which calls `decide`. Only then does an executor apply the change and log an `Event` on the Proposal. The executor reads which students to change from the Proposal's `FOR` edges in the graph, never from the caller's payload:
- `regroup` → `MERGE (:Group {id})-[:HAS_MEMBER]->(:Student)`
- `skip_ahead` → `MERGE (s)-[:MASTERED]->(c)`, with `ON CREATE SET evidence = 'teacher_override'`, so an earned mastery is never overwritten
- `assign_practice` → `(:Assignment)-[:FOR]->(:Student)` and `(:Assignment)-[:PRACTICES]->(:Construct)`
- rejected → only the Proposal's state changes

**Receipt check.** Before any LLM reply is shown, a validator confirms that every construct or misconception it names appears in that turn's tool rows. If not, it retries once, then falls back to a template.

**LLM provider chain**

1. Groq (a Llama 3.x 70B model with tool calling) as primary
2. Gemini as the second option
3. OpenRouter free models as the third
4. A template built from the receipts, so the demo never fails

Check current free-tier limits for each before relying on them. Cairn's author reported Gemini's free tier ran out fast. Cache LLM responses by prompt hash during the eval so reruns cost nothing.

**Concurrency demo (Track 02 evidence).** Run 30 students across two class graphs at once with `asyncio.gather` and the async client. Record p50 and p95 latency per tool. Then show that writes in `class_a` never wait on `class_b`, since FalkorDB serialises writes per graph.

## MCP server

A thin `unlearn_mcp.py` built on the official Python MCP SDK (`FastMCP`) exposes the same domain tools, so Claude Desktop or Cursor can drive a classroom graph. It wraps the existing tool functions; it adds no new logic.

- **Exposed:** `recall`, `root_cause`, `learning_path`, `cohorts`, `keystones`, `bridges`, `propose`. Every tool takes `class_id`.
- **Not exposed:** `decide` and any raw Cypher. Approval stays with the human in the UI, and fixed queries can't be abused.
- **Why not just FalkorDB's own MCP server:** it runs arbitrary Cypher. Domain tools with fixed queries show Track 01's "tool selection through MCP" while staying safe. Mention this choice in the README.

```
from mcp.server.fastmcp import FastMCP
from unlearn import tools

mcp = FastMCP("unlearn")

@mcp.tool()
def root_cause(class_id: str, student_id: str, construct_id: int) -> dict:
    """Deepest unmastered prerequisite with misconception evidence, plus the REQUIRES chain."""
    return tools.root_cause(class_id, student_id, construct_id)

if __name__ == "__main__":
    mcp.run()
```

Record 20 seconds of Claude Desktop calling `cohorts` then `propose` on the demo class for the video.

## API and UI

FastAPI serves the API and the UI. The UI is static HTML, CSS and JS in `api/static/`, served at `/` with no build step. Its graph panel uses Cytoscape.js, loaded from cdnjs at a pinned version with an SRI hash. One container serves everything, so there is no separate UI service.

**Endpoints**

| Method | Path | Does |
| --- | --- | --- |
| POST | `/classes/{cid}/students/{sid}/sessions` | Start a session, create the `diagnose` task, return the first question and `recall` |
| POST | `/sessions/{sess}/answer` | Body `{qid, key, explanation?}`. Returns next question or the diagnosis |
| GET | `/sessions/{sess}/diagnosis` | Root cause, chain, evidence, receipt id |
| POST | `/sessions/{sess}/remediate` | Tutor explanation, skill used, check question |
| GET | `/classes/{cid}/cohorts` | WCC groups and per-misconception groups |
| GET | `/classes/{cid}/keystones` | PageRank top 10 |
| GET | `/classes/{cid}/proposals?state=pending` | Pending approvals |
| POST | `/proposals/{pid}/decide` | Body `{decision: approved or rejected}` |
| POST | `/classes/{cid}/teacher/chat` | LLM tool loop over Teacher tools |
| GET | `/receipts/{rid}` | Cypher, params, rows and subgraph for the panel |
| GET | `/health` | Pings FalkorDB and lists graphs (use it to wake the demo) |

**Screens**

1. **Student:** question card, answer buttons, an optional "explain your thinking" box. The graph panel lights up each misconception as it's detected and draws the `REQUIRES` chain to the root cause.
2. **Tutor (same page, after diagnosis):** a "Last time you…" banner from `recall`, the explanation, the skill used, one check question.
3. **Teacher dashboard:** cohort groups, keystone constructs, pending proposals with Approve and Reject, and a chat box.
4. **Receipt drawer:** opens on every answer and shows the Cypher, params and rows behind it.
5. **Eval tab:** the results table from your eval run.

Colour misconception nodes red, mastered constructs green, the root cause amber with a thick border. Keep everything else grey so the path stands out.

## Evaluation

The eval is what moves this from top-50 to contender. Run 30 simulated students through three conditions with three random seeds, and publish the table even where a baseline wins.

**Simulator (rule-based, seeded, in `eval/simulator.py`)**

- Each student gets 1–3 planted misconceptions and one planted broken prerequisite (the true root cause).
- If an option indicates a planted misconception, pick it with probability 0.85.
- On constructs the student "knows", answer correctly with probability 0.9.
- Otherwise pick a random wrong option. Add a 10% guess rate everywhere.
- Optional: an LLM writes one-line explanations for wrong answers, to exercise `diagnose_text`.

Rule-based beats an LLM simulator here: it's free, fast and reproducible. Its weakness is that it uses the same option-to-misconception map as Unlearn, which favours Unlearn. Say this in the README and keep the noise.

**Conditions** (same question pool and same LLM for all three)

| Condition | What the model sees |
| --- | --- |
| A. No memory | The current question and answer only |
| B. Vector RAG | Full attempt history as text, plus top-10 misconceptions retrieved by embedding the question and chosen option |
| C. Unlearn | Graph tools as specified |

**Metrics**

- Top-1 and top-3 misconception accuracy against the planted set
- Root-cause accuracy: did it name the planted prerequisite?
- Questions needed before a diagnosis
- Session-2 recall: does the first tutor message name a planted misconception?
- p50 and p95 latency per diagnosis

**Results table to fill in the README**

| Metric | A. No memory | B. Vector RAG | C. Unlearn |
| --- | --- | --- | --- |
| Top-1 misconception |  |  |  |
| Top-3 misconception |  |  |  |
| Root-cause accuracy |  |  |  |
| Questions to diagnosis |  |  |  |
| Session-2 recall |  |  |  |
| p50 latency (ms) |  |  |  |

Report each cell as the mean with min–max across the three seeds. Expect Unlearn to win clearly on root cause and session-2 recall; top-1 may be close to vector RAG. Write that honestly.

## Deployment

One Docker Compose file runs two services: `falkordb` and `api`, which also serves the UI. Two profiles share one FalkorDB volume. Run one at a time:

- `dev`: FalkorDB on `127.0.0.1:6379`, for seed scripts and tests on the host, and the API on `127.0.0.1:8000`.
- `prod`: only the API is published, on `0.0.0.0:8000`. FalkorDB has no published port.

Deploy to Railway (FalkorDB's docs have a Railway page) or a small VM. Don't rely on FalkorDB Cloud's free tier for judging.

```
x-falkordb: &falkordb
  image: falkordb/falkordb:v4.20.7
  environment: [REDIS_ARGS=--requirepass ${FALKOR_PASSWORD}]
  volumes: [falkor-data:/var/lib/falkordb/data]
x-api: &api
  build: {context: ., dockerfile: api/Dockerfile}
  environment: {FALKOR_HOST: falkordb, FALKOR_PASSWORD: ${FALKOR_PASSWORD}, GROQ_API_KEY: ..., GEMINI_API_KEY: ...}
services:
  falkordb:      {<<: *falkordb, profiles: [dev],  ports: ["127.0.0.1:6379:6379"]}
  falkordb-prod: {<<: *falkordb, profiles: [prod], networks: {default: {aliases: [falkordb]}}}
  api:           {<<: *api, profiles: [dev],  ports: ["127.0.0.1:8000:8000"], depends_on: [falkordb]}
  api-prod:      {<<: *api, profiles: [prod], ports: ["8000:8000"], depends_on: [falkordb-prod]}
volumes:
  falkor-data:
```

- **Pin the image.** Pull once, test your exact queries, then pin that tag. Participants hit crashes on some 6.0.x builds.
- **Self-heal on boot.** On API startup, call `GRAPH.LIST` and seed only what is missing: no `curriculum` means a full seed, no `class_template` means 04 then 05, and no `class_demo` means 05. A wiped instance then recovers on its own. The Eedi CSVs are baked into the image, so seeding needs no network.
- **Keep FalkorDB private.** In prod, publish only the API port (8000), which also serves the UI. Don't publish 6379 or the FalkorDB Browser port.
- **Bake the embedding model into the API image** at build time, so cold starts don't download it.
- **Wake before judging.** Hit `/health` after submitting and again during judging if your host sleeps idle services.
- **Local fallback.** The README's setup is `cp .env.example .env` (set `FALKOR_PASSWORD`), then `docker compose --profile dev up -d --build`. Self-heal seeds on first boot.

## Repo structure

```
unlearn/
├── SPEC.md                     # this file
├── README.md
├── AI_USAGE.md                 # required disclosure of AI assistant use
├── LICENSE
├── docker-compose.yml
├── .env.example
├── Makefile                    # seed, eval, test, up
├── data/
│   ├── raw/                    # Eedi CSVs (gitignored, downloaded)
│   └── curated/
│       ├── requires.csv        # your prerequisite edges
│       ├── questions.json
│       └── skills.json
├── scripts/                    # 01_download … 05_new_class
├── api/
│   ├── main.py                 # FastAPI app (also serves the UI)
│   ├── static/                 # web UI: index.html, app.css, app.js (no build step)
│   ├── Dockerfile
│   └── unlearn/
│       ├── db.py               # connection, graph selection, receipts
│       ├── queries.py          # every Cypher string in one file
│       ├── tools.py            # tool functions wrapping queries
│       ├── agents/             # diagnoser.py, tutor.py, teacher.py, runner.py
│       ├── llm.py              # provider chain + cache + receipt check
│       └── unlearn_mcp.py
├── eval/                       # simulator.py, baselines.py, run_eval.py, results/
└── tests/                      # test_queries.py, test_claim_race.py
```

Keep every Cypher string in `queries.py`. The rules require the README to list the queries the product depends on, and one file makes that a copy-paste job. Commit small and often from Oct 17 onward, so the history shows the work started after Oct 15.

## Build plan

About 28 hours of work and two sleeps between now and a 22:00 IST submit on Oct 18. Each block has a "done when" test. If a block runs over by an hour, take its cut-line and move on.

| Window (IST) | Deliverable | Done when | Cut-line if behind |
| --- | --- | --- | --- |
| Oct 17, 03:30–06:00 | Repo, Compose, download, load `curriculum`, derive edges | `MATCH (m:Misconception) RETURN count(m)` returns 8117 | Skip `SHARES_MISCONCEPTION` and drop `bridges` |
| 06:00–12:00 | Sleep | — | — |
| 12:00–15:30 | Topic slice, curated `REQUIRES`, questions, skills | DAG check passes; every construct has ≥ 3 questions | 20 constructs, 3 questions each |
| 15:30–17:00 | `class_template`, indexes, embeddings, `05_new_class` | `class_demo` exists with 30 students | 10 students |
| 17:00–21:00 | `queries.py`, `tools.py`, tests | `root_cause` finds the planted cause for 3 hand-made students | Drop `SPpaths` and `bridges` |
| 21:00–Oct 18, 01:00 | Agents, handoff, approval gate, LLM chain, receipt check | CLI runs one full session end to end | Teacher agent only proposes `regroup` |
| 01:00–02:00 | MCP wrapper | Claude Desktop calls `root_cause` | Expose 3 tools only |
| 02:00–07:30 | Sleep | — | — |
| 07:30–11:30 | API, static web UI, deploy | Live URL works on your phone | Static graph render, no animation |
| 11:30–14:30 | Eval run, concurrency numbers | Results table filled | 15 students, 1 seed, conditions B and C only |
| 14:30–17:30 | README, `AI_USAGE.md`, demo video | Video under 3 minutes, uploaded | One take, no editing |
| 17:30–20:00 | dev.to blog, bug fixes | Blog published | Shorter blog |
| 20:00–22:00 | Submit, check every link in a private window | Submission confirmed | — |

**Never cut:** `root_cause`, cross-session `recall`, the approval gate, the README queries list, and at least a two-condition eval. Those are the submission's argument.

## Demo, README, blog and submission

**Demo video (2:30)**

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Two synthetic students, both 40% on fractions | "Same score, opposite problems. A chat tutor can't tell them apart." |
| 0:20–1:00 | Diagnoser asks 4 questions; misconception nodes light up; root cause traced 2 hops back; receipt drawer opens | "Every claim comes with the Cypher that proves it." |
| 1:00–1:30 | Next session: "Last time you…" banner; a handoff task moves from Diagnoser to Tutor | "Memory lives in the graph, not the prompt." |
| 1:30–1:55 | Teacher view: WCC groups, one proposal, Approve click, event logged | "Nothing changes without the teacher." |
| 1:55–2:15 | Eval table; Claude Desktop calling the MCP tools | "Measured against vector RAG and no memory." |
| 2:15–2:30 | Remove-FalkorDB line, live URL | "Take the graph out and this is just a chatbot." |

**README outline**

1. One-line pitch and the 40%/40% example
2. Remove-FalkorDB test (the line from the TL;DR)
3. Architecture diagram
4. Graph data model (copy the schema block)
5. Every Cypher query and algorithm used, from `queries.py`
6. Eval method and results table
7. How it differs from Atrium
8. Data sources, licences, Eedi attribution, what is synthetic
9. Known FalkorDB issues you hit and the workarounds
10. One-command setup
11. AI assistant disclosure (link `AI_USAGE.md`)
12. Tracks entered: 02 primary, 01 secondary

**Blog (dev.to, for the AirPods prize).** Title idea: "I gave an AI tutor a map of 8,117 ways students get maths wrong." Cover the 40%/40% example, the `root_cause` query, the eval table, and an honest "what broke" section. Add the line "Built for Graph Hacks (WeMakeDevs × FalkorDB)", as other entrants do.

**Submission checklist**

- [ ] Public repo, history starts after Oct 15
- [ ] README with data model and every Cypher query
- [ ] Demo video link works logged out
- [ ] Live URL works in a private window
- [ ] Local setup works from a fresh clone
- [ ] Tracks 02 and 01 both ticked
- [ ] `AI_USAGE.md` committed
- [ ] Eedi attribution present
- [ ] Blog published
- [ ] Submitted by 22:00 IST, Oct 18

## Risks and FalkorDB gotchas

The biggest risk is time, not FalkorDB. Hand-curating prerequisites and questions eats the afternoon if you let it. Timebox it to 3.5 hours.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Curating `REQUIRES` and questions overruns | Everything downstream slips | Hard stop at 15:30 Oct 17; take the 20-construct cut-line |
| Judges call the prerequisite graph "made up" | Credibility | Label it curated, keep it small, show the Eedi data is real |
| Simulator favours Unlearn | Eval looks rigged | Add noise, state the bias, include vector RAG with full history |
| LLM free-tier limits hit mid-eval | Eval stalls | Cache by prompt hash; graph-only template fallback |
| Host wipes or sleeps the DB | Dead demo link | Self-heal seed on boot; `/health` wake |
| A competitor ships a similar tutor | Lose uniqueness | Lead with root cause and the eval, not "tutor with memory" |

**FalkorDB behaviour to design around** (from the docs or reported by other entrants)

- **Edge direction matters.** PageRank scores incoming edges and other algorithms follow direction. Keep `REQUIRES` one way; write `SHARES_MISCONCEPTION` both ways.
- **Unnamed relationships undercount.** If a relationship in a pattern isn't referenced, FalkorDB only checks that one exists. Reference the alias when counting.
- **`LIMIT` doesn't stop eager operations before it.** `CREATE`, `SET`, `DELETE` and `MERGE` run in full first. Put `LIMIT` before writes, as in `claim`.
- **`<>` filters skip indexes.** Prefer equality and range filters on indexed properties.
- **No aggregates inside pattern comprehensions.** Aggregate in a `WITH` first.
- **Vector indexes need both `dimension` and `similarityFunction`,** and every vector must match the dimension. Insert with `vecf32()`.
- **Vector queries can't filter.** Over-fetch and filter with a `MATCH` after.
- **Betweenness samples randomly** unless you set `samplingSeed`.
- **Bugs reported on 6.0.x:** returning a never-stored property next to a count crashed the server, and `WHERE id(n) > -1` returned nothing. Test your exact queries on your pinned image.
- **Writes serialise per graph.** Good for safe claims and per-class isolation. Batch writes rather than issuing many tiny ones.

**Sources**

- [Eedi Misconceptions Graph v1.0 (Hugging Face)](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph) and its [data dictionary](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph/blob/main/docs/data-dictionary.md)
- FalkorDB docs: [PageRank](https://docs.falkordb.com/algorithms/pagerank), [algo.SPpaths](https://docs.falkordb.com/algorithms/sppath), [WCC](https://docs.falkordb.com/algorithms/wcc.html), [Betweenness](https://docs.falkordb.com/algorithms/betweenness-centrality.html), [Vector index](https://docs.falkordb.com/cypher/indexing/vector-index.html), [GRAPH.COPY](https://docs.falkordb.com/commands/graph.copy.html), [Concurrency](https://docs.falkordb.com/design/concurrency.html), [Known limitations](https://docs.falkordb.com/cypher/known-limitations.html)
- [falkordb-py client](https://github.com/FalkorDB/falkordb-py)
- [Graph Hacks rules](https://www.wemakedevs.org/hackathons/falkordb/rules)
