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
