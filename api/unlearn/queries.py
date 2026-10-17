"""Every Cypher string Unlearn runs. Parameterised only: values go in $params, never into the text."""

# --- Indexes (created before any MERGE) ---------------------------------------
# Construct and Misconception come from SPEC "Indexes". Subject/Topic/SubTopic are
# extra loader indexes so the hierarchy MERGEs don't label-scan.

CURRICULUM_INDEXES = [
    "CREATE INDEX FOR (s:Subject) ON (s.id)",
    "CREATE INDEX FOR (t:Topic) ON (t.id)",
    "CREATE INDEX FOR (st:SubTopic) ON (st.id)",
    "CREATE INDEX FOR (c:Construct) ON (c.id)",
    "CREATE INDEX FOR (m:Misconception) ON (m.id)",
]

# --- Curriculum load (scripts/02_load_curriculum.py) --------------------------

LOAD_HIERARCHY = """
UNWIND $rows AS r
MERGE (s:Subject {id:r.subject_id}) ON CREATE SET s.name = r.subject
MERGE (t:Topic {id:r.topic_id}) ON CREATE SET t.name = r.topic
MERGE (st:SubTopic {id:r.subtopic_id}) ON CREATE SET st.name = r.subtopic
MERGE (c:Construct {id:r.construct_id}) ON CREATE SET c.name = r.construct
MERGE (s)-[:HAS_TOPIC]->(t)
MERGE (t)-[:HAS_SUBTOPIC]->(st)
MERGE (st)-[:HAS_CONSTRUCT]->(c)
"""

LOAD_MISCONCEPTIONS = """
UNWIND $rows AS r
MERGE (m:Misconception {id:r.mid}) ON CREATE SET m.name = r.mname
WITH m, r
MATCH (c:Construct {id:r.cid})
MERGE (m)-[e:SEEN_IN]->(c) ON CREATE SET e.pct = r.pct
"""

# --- Derived edges (scripts/03_derive.py) -------------------------------------
# Rows already carry both directions; SET (not ON CREATE) so a re-run refreshes n.

LOAD_SHARES_MISCONCEPTION = """
UNWIND $rows AS r
MATCH (a:Construct {id:r.a}), (b:Construct {id:r.b})
MERGE (a)-[e:SHARES_MISCONCEPTION]->(b)
SET e.n = r.n
"""

# --- Counts (tests, sanity checks) --------------------------------------------
# Edge aliases are named so FalkorDB counts edges, not just existence.

COUNT_NODES_BY_LABEL = """
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS n ORDER BY label
"""

COUNT_SEEN_IN = """
MATCH (:Misconception)-[e:SEEN_IN]->(:Construct) RETURN count(e) AS n
"""

COUNT_HIERARCHY_EDGES = """
MATCH ()-[e:HAS_TOPIC|HAS_SUBTOPIC|HAS_CONSTRUCT]->() RETURN type(e) AS type, count(e) AS n ORDER BY type
"""

COUNT_SHARES_MISCONCEPTION = """
MATCH (:Construct)-[e:SHARES_MISCONCEPTION]->(:Construct) RETURN count(e) AS n, min(e.n) AS min_n
"""

ASYMMETRIC_SHARES_MISCONCEPTION = """
MATCH (a:Construct)-[e:SHARES_MISCONCEPTION]->(b:Construct)
WHERE NOT (b)-[:SHARES_MISCONCEPTION]->(a)
RETURN count(e) AS n
"""

SEEN_IN_PCT_SUMS = """
MATCH (m:Misconception)-[e:SEEN_IN]->(:Construct)
WITH m, sum(e.pct) AS total
RETURN min(total) AS min_total, max(total) AS max_total
"""

LIST_INDEXES = """
CALL db.indexes() YIELD label, properties, types, entitytype
RETURN label, properties, types, entitytype ORDER BY label
"""

# --- class_template (scripts/04_build_template.py) ----------------------------
# Indexes from SPEC "Indexes", plus the hierarchy indexes the loader MERGEs on.

CLASS_INDEXES = CURRICULUM_INDEXES + [
    "CREATE INDEX FOR (q:Question) ON (q.id)",
    "CREATE INDEX FOR (s:Student) ON (s.id)",
    "CREATE INDEX FOR (t:Task) ON (t.state)",
    "CREATE VECTOR INDEX FOR (m:Misconception) ON (m.embedding) OPTIONS {dimension:384, similarityFunction:'cosine'}",
]

# Read the topic slice out of `curriculum` (run against the curriculum graph).
SLICE_CONSTRUCTS = """
MATCH (s:Subject)-[:HAS_TOPIC]->(t:Topic)-[:HAS_SUBTOPIC]->(st:SubTopic)-[:HAS_CONSTRUCT]->(c:Construct)
WHERE (t.name = $topic AND st.name IN $subtopics) OR c.id IN $extra
RETURN s.id AS subject_id, s.name AS subject, t.id AS topic_id, t.name AS topic,
       st.id AS subtopic_id, st.name AS subtopic, c.id AS construct_id, c.name AS construct
ORDER BY construct_id
"""

SLICE_SEEN_IN = """
MATCH (m:Misconception)-[e:SEEN_IN]->(c:Construct)
WHERE c.id IN $cids
RETURN m.id AS mid, m.name AS mname, c.id AS cid, e.pct AS pct
"""

# SEEN_IN.w: the misconception's share of its weight within this graph's constructs, pct / sum(pct).
# Run on class_template after the slice is loaded, so the sum covers exactly the class slice. root_cause
# weights evidence by w: a misconception spread over several slice constructs counts less on each, but one
# whose Eedi weight mostly sits outside the slice is no longer penalised for that.
SET_SEEN_IN_WEIGHTS = """
MATCH (m:Misconception)-[si:SEEN_IN]->(:Construct)
WITH m, sum(si.pct) AS total
MATCH (m)-[si:SEEN_IN]->(:Construct)
SET si.w = CASE WHEN total > 0 THEN si.pct / total ELSE 0.0 END
"""

LOAD_REQUIRES = """
UNWIND $rows AS r
MATCH (a:Construct {id:r.construct_id}), (b:Construct {id:r.prereq_id})
MERGE (a)-[e:REQUIRES]->(b)
SET e.source = 'curated', e.weight = 1, e.note = r.note, e.confidence = r.confidence
"""

LOAD_QUESTIONS = """
UNWIND $rows AS r
MATCH (c:Construct {id:r.construct_id})
MERGE (q:Question {id:r.id})
SET q.text = r.text
MERGE (q)-[:ASSESSES]->(c)
"""

LOAD_OPTIONS = """
UNWIND $rows AS r
MATCH (q:Question {id:r.qid})
MERGE (o:Option {qid:r.qid, key:r.key})
SET o.text = r.text, o.correct = r.correct
MERGE (o)-[:OPTION_OF]->(q)
WITH o, r
WHERE r.mid IS NOT NULL
MATCH (m:Misconception {id:r.mid})
MERGE (o)-[:INDICATES]->(m)
"""

LOAD_SKILLS = """
UNWIND $rows AS r
MERGE (k:Skill {name:r.name})
SET k.description = r.description, k.success_rate = 0.5, k.uses = 0
"""

# Template is rebuilt from scratch each run, so CREATE for steps is safe.
LOAD_SKILL_STEPS = """
UNWIND $rows AS r
MATCH (k:Skill {name:r.name})
CREATE (k)-[:HAS_STEP {order:r.order}]->(:Step {text:r.text})
"""

LOAD_REMEDIATES = """
UNWIND $rows AS r
MATCH (k:Skill {name:r.name}), (m:Misconception {id:r.mid})
MERGE (k)-[:REMEDIATES]->(m)
"""

LOAD_AGENTS = """
UNWIND $names AS name
MERGE (:Agent {name:name})
"""

LOAD_EMBEDDINGS = """
UNWIND $rows AS r
MATCH (m:Misconception {id:r.id})
SET m.embedding = vecf32(r.v)
"""

COUNT_EDGES_BY_TYPE = """
MATCH ()-[e]->() RETURN type(e) AS type, count(e) AS n ORDER BY type
"""

COUNT_EMBEDDED = """
MATCH (m:Misconception) WHERE m.embedding IS NOT NULL RETURN count(m) AS n
"""

REQUIRES_MAX_DEPTH = """
MATCH p = (:Construct)-[:REQUIRES*1..8]->(:Construct)
RETURN max(length(p)) AS depth
"""

# --- class_<id> (scripts/05_new_class.py) -------------------------------------

LOAD_STUDENTS = """
UNWIND $rows AS r
MERGE (s:Student {id:r.id})
SET s.alias = r.alias
"""


# ==============================================================================
# Agent tools (SPEC "Agent tools"). Text is the SPEC's unless a comment says why not.
# ==============================================================================

# --- Diagnosis ----------------------------------------------------------------

RECORD_ATTEMPT = """
MATCH (s:Student {id:$sid}), (q:Question {id:$qid})
MATCH (o:Option {qid:$qid, key:$key})
CREATE (s)-[a:ATTEMPTED {ts:$ts, session:$sess, option:$key, correct:o.correct}]->(q)
WITH o
OPTIONAL MATCH (o)-[:INDICATES]->(m:Misconception)
RETURN o.correct AS correct, m.id AS mid, m.name AS misconception
"""

UPDATE_SHOWED = """
MATCH (s:Student {id:$sid}), (m:Misconception {id:$mid})
MERGE (s)-[e:SHOWED]->(m)
ON CREATE SET e.count = 1, e.confidence = 0.5, e.first_ts = $ts, e.last_ts = $ts
ON MATCH SET e.count = e.count + 1, e.confidence = 1 - 0.5 ^ (e.count + 1), e.last_ts = $ts
"""

DIAGNOSE_TEXT = """
CALL db.idx.vector.queryNodes('Misconception', 'embedding', 25, vecf32($v)) YIELD node, score
MATCH (node)-[e:SEEN_IN]->(:Construct {id:$cid})
RETURN node.id AS id, node.name AS name, score, e.pct AS pct
ORDER BY score ASC LIMIT 3
"""

# Changed from SPEC (decision on REVIEW item 4): exclude only questions attempted in the current session, so
# session 2 can ask about the root again. Never-attempted questions first, then least recently attempted,
# then the SPEC's probe ordering.
NEXT_QUESTION = """
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
"""

QUESTION_OPTIONS = """
MATCH (o:Option)-[:OPTION_OF]->(:Question {id:$qid})
RETURN o.key AS key, o.text AS text ORDER BY key
"""

# MASTERED is decided in Python (SPEC): two correct answers on the construct's
# questions and no SHOWED above 0.6 on that construct's misconceptions.
MASTERY_EVIDENCE = """
MATCH (q:Question {id:$qid})-[:ASSESSES]->(c:Construct)
MATCH (s:Student {id:$sid})
OPTIONAL MATCH (s)-[a:ATTEMPTED]->(:Question)-[:ASSESSES]->(c)
WITH s, c, sum(CASE WHEN a.correct THEN 1 ELSE 0 END) AS correct
OPTIONAL MATCH (s)-[e:SHOWED]->(:Misconception)-[:SEEN_IN]->(c)
RETURN c.id AS cid, correct, max(e.confidence) AS max_confidence
"""

MARK_MASTERED = """
MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})
MERGE (s)-[m:MASTERED]->(c)
ON CREATE SET m.ts = $ts, m.evidence = $evidence
"""

# --- Root cause ---------------------------------------------------------------

ROOT_CAUSE = """
MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})
MATCH p = (c)-[:REQUIRES*1..4]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
WITH s, pre, min(length(p)) AS depth
OPTIONAL MATCH (s)-[e:SHOWED]->(m:Misconception)-[si:SEEN_IN]->(pre)
WITH pre, depth, sum(coalesce(e.count, 0) * coalesce(e.confidence, 0.0) * coalesce(si.w, 0.0)) AS evidence, collect(DISTINCT m.name) AS miscs
WHERE evidence > 0
RETURN pre.id AS id, pre.name AS name, depth, evidence, miscs
ORDER BY evidence DESC, depth DESC LIMIT 3
"""

# Changed from SPEC: v4.20.7 can't ORDER BY length(p) when p isn't projected
# ("Unable to locate a value with alias p"), so the length is returned as hops.
ROOT_CAUSE_CHAIN = """
MATCH p = (c:Construct {id:$cid})-[:REQUIRES*1..4]->(:Construct {id:$pid})
RETURN [n IN nodes(p) | n.name] AS chain, [n IN nodes(p) | n.id] AS ids, length(p) AS hops
ORDER BY hops ASC LIMIT 1
"""

PROBE_FRONTIER = """
MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})
MATCH p = (c)-[:REQUIRES*1..4]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
AND NOT (s)-[:ATTEMPTED]->(:Question)-[:ASSESSES]->(pre)
WITH pre, max(length(p)) AS depth
RETURN pre.id AS id, pre.name AS name, depth
ORDER BY depth DESC LIMIT 3
"""

# --- Teaching and memory ------------------------------------------------------

LEARNING_PATH = """
MATCH (s:Student {id:$sid}), (t:Construct {id:$tid})
MATCH p = (t)-[:REQUIRES*0..6]->(pre:Construct)
WHERE NOT (s)-[:MASTERED]->(pre)
WITH pre, max(length(p)) AS depth
RETURN pre.id AS id, pre.name AS name, depth
ORDER BY depth DESC
"""

LEARNING_PATH_SP = """
MATCH (t:Construct {id:$tid}), (m:Construct {id:$mid})
CALL algo.SPpaths({sourceNode: t, targetNode: m, relTypes: ['REQUIRES'], weightProp: 'weight', relDirection: 'outgoing', maxLen: 6})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.name] AS chain, pathWeight
"""

RECALL = """
MATCH (s:Student {id:$sid})-[e:SHOWED]->(m:Misconception)
WHERE e.confidence > 0.6
OPTIONAL MATCH (s)-[:HAD_SESSION]->(:Session)-[:HAD_EVENT]->(ev:Event)-[:ABOUT]->(m)
WITH m, e, ev ORDER BY ev.ts DESC
WITH m, e, collect(ev.summary) AS events
RETURN m.name AS misconception, e.count AS times, e.last_ts AS last_seen, events[0..3] AS recent
ORDER BY last_seen DESC LIMIT 5
"""

PICK_SKILL = """
MATCH (k:Skill)-[:REMEDIATES]->(:Misconception {id:$mid})
RETURN k.name AS skill, k.success_rate AS rate, k.uses AS uses
ORDER BY rate DESC LIMIT 1
"""

UPDATE_SKILL = """
MATCH (k:Skill {name:$name})
SET k.success_rate = (k.success_rate * (k.uses + 2) + $ok) / (k.uses + 3)
SET k.uses = k.uses + 1
"""

SKILL_BY_NAME = """
MATCH (k:Skill {name:$name})
RETURN k.name AS skill, k.success_rate AS rate, k.uses AS uses
"""

# Not one of the 16 tools: session/event writes the agents need for episodic memory.
START_SESSION = """
MATCH (s:Student {id:$sid})
OPTIONAL MATCH (s)-[:HAD_SESSION]->(old:Session)
WITH s, count(old) AS k
CREATE (s)-[:HAD_SESSION]->(se:Session {id:$sess, ts:$ts, n:k + 1})
RETURN se.id AS id, se.n AS n
"""

LOG_EVENT = """
MATCH (se:Session {id:$sess})
CREATE (se)-[:HAD_EVENT]->(ev:Event {id:$id, type:$type, ts:$ts, summary:$summary})
WITH ev
OPTIONAL MATCH (m:Misconception {id:$mid})
OPTIONAL MATCH (c:Construct {id:$cid})
FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | CREATE (ev)-[:ABOUT]->(m))
FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | CREATE (ev)-[:ABOUT]->(c))
RETURN ev.id AS id
"""

# --- Teacher analytics --------------------------------------------------------

COHORTS_CLEAR = """
MATCH ()-[g:SHARES_GAP]->() DELETE g
"""

COHORTS_LINK = """
MATCH (a:Student)-[e1:SHOWED]->(m:Misconception)<-[e2:SHOWED]-(b:Student)
WHERE a.id < b.id AND e1.confidence > 0.6 AND e2.confidence > 0.6
WITH a, b, collect(m.name) AS miscs
CREATE (a)-[:SHARES_GAP {miscs: miscs}]->(b)
"""

# Added to SPEC: `ids` alongside the aliases, so the Teacher agent can propose for those students.
COHORTS_WCC = """
CALL algo.WCC({nodeLabels: ['Student'], relationshipTypes: ['SHARES_GAP']}) YIELD node, componentId
WITH componentId, collect(node.alias) AS students, collect(node.id) AS ids
WHERE size(students) > 1
RETURN componentId, students, ids ORDER BY size(students) DESC
"""

KEYSTONES = """
CALL algo.pageRank('Construct', 'REQUIRES') YIELD node, score
RETURN node.id AS id, node.name AS name, score ORDER BY score DESC LIMIT 10
"""

# SPEC: write scores back with a separate UNWIND rather than SET after YIELD.
SET_PAGERANK = """
UNWIND $rows AS r
MATCH (c:Construct {id:r.id})
SET c.pagerank = r.score
"""

# Runs on `curriculum`, not a class graph.
BRIDGES = """
CALL algo.betweenness({nodeLabels: ['Construct'], relationshipTypes: ['SHARES_MISCONCEPTION'], samplingSize: 256, samplingSeed: 42})
YIELD node, score
RETURN node.name AS name, score ORDER BY score DESC LIMIT 10
"""

# --- Coordination -------------------------------------------------------------

CLAIM = """
MATCH (t:Task {state:'submitted'})-[:ASSIGNED_TO]->(:Agent {name:$agent})
WITH t ORDER BY t.created_ts LIMIT 1
SET t.state = 'working', t.claimed_by = $worker
RETURN t.id AS id, t.kind AS kind
"""

# Added to SPEC: the new task copies construct_id and session from prev in the same write, so a
# worker that claims it immediately never sees a task without its context.
HANDOFF = """
MATCH (prev:Task {id:$prev}), (s:Student {id:$sid}), (a:Agent {name:$to})
CREATE (t:Task {id:$id, kind:$kind, state:'submitted', created_ts:$ts, construct_id:prev.construct_id, session:prev.session})
CREATE (t)-[:ABOUT]->(s), (t)-[:ASSIGNED_TO]->(a), (t)-[:HANDED_OFF_FROM]->(prev)
SET prev.state = 'completed'
RETURN t.id AS id
"""

PROPOSE = """
CREATE (p:Proposal {id:$id, kind:$kind, state:'pending', payload:$json, created_ts:$ts})
WITH p UNWIND $sids AS sid
MATCH (s:Student {id:sid}) CREATE (p)-[:FOR]->(s)
"""

DECIDE = """
MATCH (p:Proposal {id:$id, state:'pending'})
SET p.state = $decision, p.decided_ts = $ts
RETURN p.kind AS kind, p.payload AS payload
"""

# Not one of the 16 tools: the first task of a chain (handoff needs a previous task).
CREATE_TASK = """
MATCH (s:Student {id:$sid}), (a:Agent {name:$agent})
CREATE (t:Task {id:$id, kind:$kind, state:'submitted', created_ts:$ts, construct_id:$cid, session:$sess})
CREATE (t)-[:ABOUT]->(s), (t)-[:ASSIGNED_TO]->(a)
RETURN t.id AS id
"""

SHOWED_ON_WEIGHTS = """
MATCH (:Misconception {id:$mid})-[si:SEEN_IN]->(c:Construct)
RETURN c.id AS cid, si.pct AS pct, si.w AS w ORDER BY cid
"""

STUDENT_SHOWED = """
MATCH (:Student {id:$sid})-[e:SHOWED]->(m:Misconception)
RETURN m.id AS mid, m.name AS name, e.count AS count, e.confidence AS confidence
ORDER BY e.confidence DESC, m.id
"""

TASK_STATE = """
MATCH (t:Task {id:$id}) RETURN t.state AS state, t.claimed_by AS claimed_by
"""

REQUIRES_PROPS = """
MATCH (:Construct)-[e:REQUIRES]->(:Construct)
RETURN count(e) AS n, collect(DISTINCT e.weight) AS weights, collect(DISTINCT e.source) AS sources
"""

# --- Agent helpers (not among the 16 tools) -----------------------------------

STUDENT_SESSIONS = """
MATCH (:Student {id:$sid})-[:HAD_SESSION]->(se:Session)
RETURN se.id AS id, se.n AS n, se.ts AS ts ORDER BY n
"""

TASK_CONTEXT = """
MATCH (t:Task {id:$id})-[:ABOUT]->(s:Student)
OPTIONAL MATCH (s)-[:HAD_SESSION]->(se:Session {id:t.session})
RETURN t.id AS id, t.kind AS kind, t.state AS state, s.id AS student_id, t.construct_id AS construct_id,
       t.session AS session, se.n AS session_n, t.pending_qid AS pending_qid, t.pending_cid AS pending_cid,
       t.skill AS skill, t.mid AS mid, t.root_id AS root_id
"""

COMPLETE_TASK = """
MATCH (t:Task {id:$id}) SET t.state = 'completed' RETURN t.id AS id
"""

FAIL_TASK = """
MATCH (t:Task {id:$id}) SET t.state = 'failed', t.error = $error RETURN t.id AS id
"""

# Tasks in the chain that starts at $root which are still open.
CHAIN_OPEN = """
MATCH (t:Task)-[:HANDED_OFF_FROM*0..]->(:Task {id:$root})
WHERE t.state IN ['submitted', 'working']
RETURN count(t) AS open
"""

CHAIN = """
MATCH p = (t:Task)-[:HANDED_OFF_FROM*0..]->(:Task {id:$root})
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(a:Agent)
RETURN t.id AS id, t.kind AS kind, t.state AS state, a.name AS agent, length(p) AS step
ORDER BY step
"""

# The student's misconceptions on one construct, strongest weighted evidence first (root_cause's weighting, si.w).
SHOWED_ON = """
MATCH (:Student {id:$sid})-[e:SHOWED]->(m:Misconception)-[si:SEEN_IN]->(:Construct {id:$cid})
RETURN m.id AS mid, m.name AS name, e.count AS count, e.confidence AS confidence,
       e.count * e.confidence * si.w AS evidence
ORDER BY evidence DESC, m.id
"""

SKILL_STEPS = """
MATCH (:Skill {name:$name})-[h:HAS_STEP]->(st:Step)
RETURN h.order AS order, st.text AS text ORDER BY order
"""

# Every construct and misconception name in a class graph: the vocabulary the receipt check scans for.
NAME_VOCABULARY = """
MATCH (n) WHERE n:Construct OR n:Misconception
RETURN labels(n)[0] AS label, n.id AS id, n.name AS name
"""

PROPOSALS = """
MATCH (p:Proposal)
WHERE $state IS NULL OR p.state = $state
OPTIONAL MATCH (p)-[:FOR]->(s:Student)
RETURN p.id AS id, p.kind AS kind, p.state AS state, p.payload AS payload, p.created_ts AS created_ts,
       collect(s.id) AS students
ORDER BY created_ts
"""

# Demo reset: drop one student's memory and coordination state so session 1 can be replayed.
RESET_STUDENT_SESSIONS = """
MATCH (:Student {id:$sid})-[:HAD_SESSION]->(se:Session)
OPTIONAL MATCH (se)-[:HAD_EVENT]->(ev:Event)
DETACH DELETE se, ev
"""

RESET_STUDENT_EDGES = """
MATCH (:Student {id:$sid})-[r:ATTEMPTED|SHOWED|MASTERED|SHARES_GAP]-()
DELETE r
"""

RESET_STUDENT_TASKS = """
MATCH (t:Task)-[:ABOUT]->(:Student {id:$sid})
DETACH DELETE t
"""

RESET_STUDENT_PROPOSALS = """
MATCH (p:Proposal)-[:FOR]->(:Student {id:$sid})
OPTIONAL MATCH (p)-[:HAD_EVENT]->(ev:Event)
OPTIONAL MATCH (a:Assignment {proposal:p.id})
DETACH DELETE p, ev, a
"""

RESET_STUDENT_GROUPS = """
MATCH (:Group)-[r:HAS_MEMBER]->(:Student {id:$sid})
DELETE r
"""

# --- Approval executor: runs only after decide(approved) ------------------------

EXEC_REGROUP = """
MATCH (p:Proposal {id:$pid})-[:FOR]->(s:Student)
MERGE (g:Group {id:$gid})
MERGE (g)-[:HAS_MEMBER]->(s)
RETURN g.id AS group_id, collect(s.id) AS members
"""

EXEC_SKIP_AHEAD = """
MATCH (p:Proposal {id:$pid})-[:FOR]->(s:Student), (c:Construct {id:$cid})
MERGE (s)-[m:MASTERED]->(c)
ON CREATE SET m.ts = $ts, m.evidence = 'teacher_override'
RETURN s.id AS student_id, c.id AS construct_id, m.evidence AS evidence
"""

EXEC_ASSIGN_PRACTICE = """
MATCH (p:Proposal {id:$pid}), (c:Construct {id:$cid})
CREATE (a:Assignment {id:$aid, ts:$ts, proposal:$pid})
CREATE (a)-[:PRACTICES]->(c)
WITH a, p
MATCH (p)-[:FOR]->(s:Student)
CREATE (a)-[:FOR]->(s)
RETURN a.id AS assignment_id, collect(s.id) AS students
"""

LOG_PROPOSAL_EVENT = """
MATCH (p:Proposal {id:$pid})
CREATE (p)-[:HAD_EVENT]->(ev:Event {id:$id, type:$type, ts:$ts, summary:$summary})
WITH ev
OPTIONAL MATCH (c:Construct {id:$cid})
FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | CREATE (ev)-[:ABOUT]->(c))
RETURN ev.id AS id
"""

# Read-backs for the approval tests.
GROUP_MEMBERS = """
MATCH (g:Group {id:$gid})-[:HAS_MEMBER]->(s:Student) RETURN s.id AS id ORDER BY id
"""

ASSIGNMENTS_FOR = """
MATCH (a:Assignment)-[:FOR]->(:Student {id:$sid})
MATCH (a)-[:PRACTICES]->(c:Construct)
RETURN a.id AS id, c.id AS construct_id
"""

MASTERED_EDGE = """
MATCH (:Student {id:$sid})-[m:MASTERED]->(:Construct {id:$cid}) RETURN m.evidence AS evidence
"""

PROPOSAL_EVENTS = """
MATCH (:Proposal {id:$pid})-[:HAD_EVENT]->(ev:Event) RETURN ev.id AS id, ev.type AS type, ev.summary AS summary
"""

COUNT_LABELS = """
MATCH (n) WHERE n:Group OR n:Assignment RETURN labels(n)[0] AS label, count(n) AS n
"""

# --- Steppable agents: per-session state lives on the Task and in this session's ATTEMPTED edges ----------

# Claim one specific task (an HTTP request driving its own session). Race-safe like CLAIM.
# Read-only check before a poller claims: cheap, and it never recreates a graph deleted under it.
OPEN_TASKS_FOR = """
MATCH (t:Task {state:'submitted'})-[:ASSIGNED_TO]->(:Agent {name:$agent})
RETURN count(t) AS n
"""

CLAIM_TASK = """
MATCH (t:Task {id:$id, state:'submitted'})-[:ASSIGNED_TO]->(:Agent {name:$agent})
SET t.state = 'working', t.claimed_by = $worker
RETURN t.id AS id, t.kind AS kind
"""

# CLAIM limited to one session, so a simulated session's workers never take a live session's tasks.
CLAIM_IN_SESSION = """
MATCH (t:Task {state:'submitted', session:$sess})-[:ASSIGNED_TO]->(:Agent {name:$agent})
WITH t ORDER BY t.created_ts LIMIT 1
SET t.state = 'working', t.claimed_by = $worker
RETURN t.id AS id, t.kind AS kind
"""

# The question a task is waiting on (null clears it).
SET_PENDING = """
MATCH (t:Task {id:$id}) SET t.pending_qid = $qid, t.pending_cid = $cid RETURN t.id AS id
"""

# What the Tutor taught, so the check answer can update the right skill in a later request.
SET_TUTOR_PLAN = """
MATCH (t:Task {id:$id}) SET t.skill = $skill, t.mid = $mid, t.root_id = $root RETURN t.id AS id
"""

SESSION_TASKS = """
MATCH (t:Task {session:$sess})
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(a:Agent)
RETURN t.id AS id, t.kind AS kind, t.state AS state, t.pending_qid AS pending_qid, a.name AS agent,
       t.created_ts AS created_ts
ORDER BY created_ts
"""

# This session's answers in order: the Diagnoser's search state is derived from these.
SESSION_ATTEMPTS = """
MATCH (:Student {id:$sid})-[a:ATTEMPTED {session:$sess}]->(q:Question)-[:ASSESSES]->(c:Construct)
RETURN q.id AS qid, c.id AS construct_id, a.correct AS correct, a.ts AS ts
ORDER BY ts, qid
"""

# Answered correctly this session, plus everything those constructs depend on: ruled out as the root cause.
SESSION_RULED_OUT = """
MATCH (:Student {id:$sid})-[:ATTEMPTED {session:$sess, correct:true}]->(:Question)-[:ASSESSES]->(c:Construct)
MATCH (c)-[:REQUIRES*0..6]->(d:Construct)
RETURN collect(DISTINCT d.id) AS ids
"""

SESSION_LOOKUP = """
MATCH (s:Student)-[:HAD_SESSION]->(se:Session {id:$sess})
RETURN s.id AS student_id, se.n AS n, se.ts AS ts
"""

# --- API / UI reads ------------------------------------------------------------------------------------

# The REQUIRES subgraph under a target: the student's slice for the graph panel.
SLICE_FOR_TARGET = """
MATCH (:Construct {id:$tid})-[:REQUIRES*0..6]->(c:Construct)
RETURN DISTINCT c.id AS id, c.name AS name
"""

SLICE_EDGES = """
MATCH (:Construct {id:$tid})-[:REQUIRES*0..6]->(a:Construct)-[:REQUIRES]->(b:Construct)
RETURN DISTINCT a.id AS src, b.id AS dst
"""

STUDENT_SHOWED_ON_SLICE = """
MATCH (:Student {id:$sid})-[e:SHOWED]->(m:Misconception)-[si:SEEN_IN]->(c:Construct)
WHERE c.id IN $cids
RETURN m.id AS mid, m.name AS name, e.count AS count, e.confidence AS confidence, c.id AS cid, si.w AS w
"""

STUDENT_MASTERED_ON_SLICE = """
MATCH (:Student {id:$sid})-[m:MASTERED]->(c:Construct)
WHERE c.id IN $cids
RETURN c.id AS id, m.evidence AS evidence
"""

CLASS_STUDENTS = """
MATCH (s:Student)
OPTIONAL MATCH (s)-[:HAD_SESSION]->(se:Session)
RETURN s.id AS id, s.alias AS alias, count(se) AS sessions
ORDER BY id
"""

# Constructs that have prerequisites, deepest chains first: the session targets a teacher can pick.
TARGETS = """
MATCH (st:SubTopic)-[:HAS_CONSTRUCT]->(c:Construct)-[:REQUIRES]->(:Construct)
WITH DISTINCT st, c
MATCH p = (c)-[:REQUIRES*1..6]->(:Construct)
RETURN c.id AS id, c.name AS name, st.name AS subtopic, max(length(p)) AS depth
ORDER BY depth DESC, name
"""

PROPOSAL_LOOKUP = """
MATCH (p:Proposal {id:$id}) RETURN p.id AS id, p.state AS state
"""

COUNT_NODES = """
MATCH (n) RETURN count(n) AS n
"""

# --- Demo scenario (scripts/demo_scenario.py) ------------------------------------------------------------

# Students with a planted simulator profile. Ground truth for the simulated answers only: no agent query
# reads the sim_* properties.
LOAD_STUDENT_PROFILES = """
UNWIND $rows AS r
MERGE (s:Student {id:r.id})
SET s.alias = r.alias, s.sim_root = r.root, s.sim_target = r.target, s.sim_misconceptions = r.mids,
    s.sim_seed = r.seed
"""

STUDENT_SIM_PROFILE = """
MATCH (s:Student {id:$sid})
RETURN s.sim_root AS root, s.sim_target AS target, s.sim_misconceptions AS mids, s.sim_seed AS seed
"""

# Scores on the fixed fractions check: answers recorded in a 'quiz:<student>' session (not a tutoring Session).
QUIZ_SCORES = """
MATCH (s:Student)-[a:ATTEMPTED]->(:Question)
WHERE a.session STARTS WITH 'quiz:'
RETURN s.id AS id, sum(CASE WHEN a.correct THEN 1 ELSE 0 END) AS correct, count(a) AS total
"""

SESSION_SCORE = """
MATCH (:Student {id:$sid})-[a:ATTEMPTED {session:$sess}]->(:Question)
RETURN sum(CASE WHEN a.correct THEN 1 ELSE 0 END) AS correct, count(a) AS total
"""

# --- Eval (eval/run_eval.py, eval/baselines.py) -------------------------------------------------------

# Condition B's retriever and the eval's judge: nearest misconceptions to a text, over the whole class graph
# (no construct filter, unlike diagnose_text). Score is a cosine distance, lower is closer.
NEAREST_MISCONCEPTIONS = """
CALL db.idx.vector.queryNodes('Misconception', 'embedding', $k, vecf32($v)) YIELD node, score
RETURN node.id AS id, node.name AS name, score
ORDER BY score ASC
"""

CLASS_CONSTRUCTS = """
MATCH (c:Construct) RETURN c.id AS id, c.name AS name ORDER BY id
"""

# --- Concurrency demo (eval/concurrency.py) --------------------------------------------------------------

# A small write: what a probe times while other writers run.
CONC_PROBE_WRITE = """
MERGE (p:Probe {id:$id}) SET p.ts = $ts RETURN p.id AS id
"""

# A deliberately heavy write (creates $n nodes) to keep a graph's write lock busy.
CONC_HEAVY_WRITE = """
UNWIND range(1, $n) AS i CREATE (:Load {i:i, w:$w})
"""
