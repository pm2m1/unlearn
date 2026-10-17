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

NEXT_QUESTION = """
MATCH (s:Student {id:$sid})
MATCH (q:Question)-[:ASSESSES]->(:Construct {id:$cid})
WHERE NOT (s)-[:ATTEMPTED]->(q)
MATCH (o:Option)-[:OPTION_OF]->(q)
OPTIONAL MATCH (o)-[:INDICATES]->(m:Misconception)
OPTIONAL MATCH (s)-[e:SHOWED]->(m)
WITH q, count(DISTINCT m) AS probes, sum(CASE WHEN m IS NOT NULL AND e IS NULL THEN 1 ELSE 0 END) AS unprobed
RETURN q.id AS id, q.text AS text, probes, unprobed
ORDER BY unprobed DESC, probes DESC LIMIT 1
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
OPTIONAL MATCH (s)-[e:SHOWED]->(m:Misconception)-[:SEEN_IN]->(pre)
WITH pre, depth, sum(coalesce(e.count, 0) * coalesce(e.confidence, 0.0)) AS evidence, collect(DISTINCT m.name) AS miscs
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

COHORTS_WCC = """
CALL algo.WCC({nodeLabels: ['Student'], relationshipTypes: ['SHARES_GAP']}) YIELD node, componentId
WITH componentId, collect(node.alias) AS students
WHERE size(students) > 1
RETURN componentId, students ORDER BY size(students) DESC
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

HANDOFF = """
MATCH (prev:Task {id:$prev}), (s:Student {id:$sid}), (a:Agent {name:$to})
CREATE (t:Task {id:$id, kind:$kind, state:'submitted', created_ts:$ts})
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
CREATE (t:Task {id:$id, kind:$kind, state:'submitted', created_ts:$ts})
CREATE (t)-[:ABOUT]->(s), (t)-[:ASSIGNED_TO]->(a)
RETURN t.id AS id
"""
