# Unlearn in one page

**Pitch.** Asha and Ben both score 40% on fractions. Asha can't find a lowest common multiple, a skill from another topic two steps below the question she got wrong. Ben changes only the denominator when he makes an equivalent fraction. Unlearn asks a few adaptive questions, walks a prerequisite graph back to the skill that broke, remembers it next session, and shows the Cypher behind every claim.

## The graph model

- **Three kinds of graph in one FalkorDB instance:**
  - `curriculum`: all of Eedi, read-only. 8,117 misconceptions.
  - `class_template`: the Fractions slice. 40 constructs, 410 misconceptions, 57 curated `REQUIRES` edges, 120 questions.
  - `class_<id>`: one per classroom, made with `GRAPH.COPY`. The copy carries all 9 indexes, the vector index included.
- **Four layers:**
  - **Curriculum:** `Construct`, `Misconception -[:SEEN_IN {pct, w}]-> Construct`, and `Construct -[:REQUIRES]-> Construct` (needs → prerequisite).
  - **Assessment:** `Question`, `Option -[:INDICATES]-> Misconception`. Wrong options only.
  - **Memory:**
    - `ATTEMPTED` (episodic);
    - `SHOWED {count, confidence}` and `MASTERED` (semantic);
    - `Skill -[:HAS_STEP]-> Step` with a `success_rate` (procedural);
    - `Session` / `Event`.
  - **Coordination:** `Task` (claimed, handed off), `Proposal` (waits for a human), `Agent`.
- **One sentence for judges:** the agents keep no state in Python. Each HTTP request runs one step, and that step reads its state back from the graph.

## `root_cause`, line by line

| Line | What it does |
| --- | --- |
| `MATCH (s:Student {id:$sid}), (c:Construct {id:$cid})` | The student and the skill they're working on. |
| `MATCH p = (c)-[:REQUIRES*1..4]->(pre:Construct)` | Every prerequisite up to 4 hops below it. |
| `WHERE NOT (s)-[:MASTERED]->(pre)` | Skip skills the student has already shown they can do. |
| `WITH s, pre, min(length(p)) AS depth` | One row per prerequisite, with its shortest distance from the target. |
| `OPTIONAL MATCH (s)-[e:SHOWED]->(m:Misconception)-[si:SEEN_IN]->(pre)` | Misconceptions this student showed that belong to that prerequisite. |
| `sum(e.count * e.confidence * si.w) AS evidence` | Evidence: how often, how surely, how specific to this skill. |
| `WHERE evidence > 0` | Only prerequisites with evidence against them. |
| `ORDER BY evidence DESC, depth DESC LIMIT 3` | Strongest first. Ties go to the deeper skill, since the deepest broken one is the cause. |

A second query (`ROOT_CAUSE_CHAIN`) returns the shortest `REQUIRES` path from the target to the winner. That path is the chain shown on screen.

## The Diagnoser's search

The SPEC's version probed the deepest prerequisites first. On seed 0 that named the planted root top-1 for only 8 of 30 students: the 6-question budget went on deep skills the student already knew. The Diagnoser now searches **top-down** using `learning_path`:

1. Ask about the closest prerequisite of the target that hasn't been asked this session.
2. **Right answer:** that skill and everything it depends on are ruled out.
3. **Wrong answer:** it becomes a suspect, and the search continues below it.
4. When nothing is left below the deepest suspect, ask about it again to confirm.
5. **Stop** when `root_cause`'s top evidence is ≥ 1.5, leads the runner-up by ≥ 0.5, and is that deepest suspect. Otherwise stop after 6 questions.

Asha's actual run:

| Question on | Result | Effect |
| --- | --- | --- |
| 427, unlike fractions | wrong | 427 becomes a suspect |
| 345, LCM | wrong | 345 becomes a suspect, one level deeper |
| 342, multiples | right | 342 is ruled out |
| 345 again, twice | wrong both times | confirmed |

Root 345 after 5 questions, 2 levels down.

## Evidence weighting (`SEEN_IN.w`)

- **The weight.** Eedi's `pct` says how often a misconception shows up on a construct. `w = pct / Σ pct` over the class slice's constructs, so a misconception's weights in a class sum to 1.
  - **Specific misconception, w = 1.0:** "Finds a common multiple but not the lowest" appears only on 345.
  - **Generic misconception, split weight:** "Confuses factors and multiples" scores 0.40 on 345, 0.38 on 342, 0.15 on 331 and 0.06 on 338. One wrong answer no longer counts as full evidence against four skills.
- **Confidence.** It rises with repeats: 0.5 → 0.75 → 0.875 (`1 − 0.5^count`).
- **Worked example.** Two hits of a w = 1 misconception score 2 × 0.75 × 1 = **1.5**, exactly the stop threshold. The thresholds (1.5 / 0.5) are the SPEC's own and were not tuned. Looser ones scored slightly higher on the simulator and were rejected for that reason.

## The recall rule

- **What `recall` returns:** every misconception the student has shown (count ≥ 1).
- **How it ranks them:**
  1. Ones on the root cause the latest diagnosis named, by `SEEN_IN.w`.
  2. Then by confidence.
  3. Then by recency.
- **Why:** the tutor should open with what it diagnosed last time.
- **The SPEC's rule** (seen twice, newest first) left 58 of 90 simulated students with nothing to recall.
- **Measured on the same histories:**

  | Rule | Session-2 opening names a planted misconception | Named misconceptions that were planted |
  | --- | --- | --- |
  | SPEC rule | 28% | 78% |
  | Strongest first | 56% | 31% |
  | **Root first (current)** | **68%** | **45%** |

- **Say it plainly:** the rule was chosen after seeing these numbers. The cost is precision, because one-off slips get named too.

## Why FalkorDB (and what B+ shows)

- **The obvious objection:** "just paste the graph into the prompt." That is condition **B+**: B's prompt plus every `REQUIRES` edge and every construct's misconceptions with their weights (~22k tokens), on the same local model (qwen3.5 27B).
- **Result:**

  B+ ran on seed 0 only, so every comparison with it uses seed 0's 30 students (the same students in each column):

  | Seed 0, n=30 each | B+ | B | Unlearn (C) |
  | --- | --- | --- | --- |
  | Root cause | 40% | 30% | 63% |
  | Top-1 misconception | 23% | 13% | 50% |
  | Top-3 misconception | 47% | 27% | 73% |
  | p50 time per diagnosis | 113 s | 7.7 s | 50 ms |

  Over all three seeds (90 students), without B+: C scores 72% on root cause against 37% for B and 32% for A.

  The graph's *knowledge* helps an LLM a little. The *traversal* (rule out, descend, weigh evidence, remember) is what gets you to the root.
- **What the graph does that a prompt can't:**
  - Memory persists across sessions (`SHOWED`, `Event`).
  - Agents coordinate through `Task` and `Proposal` nodes. `CLAIM` is race-safe.
  - Each class is an isolated graph whose writes don't queue behind another class's.
  - Vector search, WCC, PageRank, betweenness and shortest paths run in the same engine as the memory.
- **Remove-FalkorDB test:** take the graph away and there's no grounding, no root-cause traversal, no memory and no handoffs. It's a chatbot.

## Known weaknesses (say them before a judge does)

- **Synthetic students.**
  - All 90 eval students are simulated. The simulator picks wrong answers through the same option-to-misconception map Unlearn reads, which favours Unlearn.
  - A 10% guess rate and planted misconceptions picked only 85% of the time blunt that bias but don't remove it.
  - No real student has used it.
- **Curated prerequisites.**
  - The 57 `REQUIRES` edges were drafted with AI help and reviewed by hand. The review deleted 2 edges and removed 9 question options (`REVIEW.md`, section 0). 10 of the 57 are still marked medium or low confidence.
  - Logged but not changed: 429, 437 and 3241 probably also need the multiple-case skill (425 or 433), and 3328's negative-numbers prerequisite is outside the slice.
  - `root_cause` is only as good as those edges.
  - Place value was left out on purpose.
- **Baselines are capped by retrieval.**
  - A planted misconception is on A's candidate list for 23% of students and on B's for 20%, so their misconception scores can't go higher whatever the model does.
  - B+ is not capped: it is scored on every ID in its prompt (410 misconceptions, 40 constructs). It was first scored on B's list only, which was corrected on Oct 18 from the cached outputs (on the pre-review data). Its top-3 went from 20% to 33%; its root cause was unchanged.
  - Root-cause candidates (the target's ~7 prerequisites) favour the baselines: a random pick is right 23% of the time.
- **Model size.** The baselines ran on a 27B local model. A stronger model may narrow the gap on naming misconceptions.
- **Questions run out.** There are only 3 questions per construct and `next_question` never repeats one, so session 2 sometimes can't re-ask the root.
- **Free-tier LLMs.** Gemini allows 20 requests per model per day. After that the words come from templates (the facts never change, because they come from the graph).
