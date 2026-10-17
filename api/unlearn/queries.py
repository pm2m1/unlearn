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
