# Review for Parth — Phase 2 drafts

Everything in `data/curated/` is a **DRAFT** written by Claude Code. **Parth reviewed sections 1–3 on Oct 18, 2026.** His decisions and reasons are in section 0. They were **applied on Oct 18**: `scripts/author_questions.py` and `requires.csv` were edited, the graphs rebuilt, and the eval re-run on the new data.
Suggested order: REQUIRES edges (they drive `root_cause`), then the stretch distractors, then the 10-question spot check.

## 0. Decisions (Parth, Oct 18, 2026, applied)

**Summary:**
- **Edges:** 10 KEEP, 2 DELETE.
- **Distractors:** 6 OK, 8 REMOVE.
- **Spot checks:** 9 PASS, 1 FAIL, fixed by removing one option.
- **Applied:** 2 edges deleted (59 → 57; 10 of 57 are not "high") and 9 options removed (8 REMOVEs plus the FAIL fix). The 9 questions were reshuffled by `author_questions.py` as usual.

### REQUIRES edges (section 1)

| # | Edge (needs → prerequisite) | Decision | Reason |
| --- | --- | --- | --- |
| 1 | 3587 → 408 | KEEP | 408's square question only works because the wholes are the same size, which is the same idea 3587 tests. |
| 2 | 409 → 408 | KEEP | Concrete before abstract is the standard teaching order; a student who can't see 1/4 = 2/8 in a square has nothing to anchor the numeric rule to. |
| 3 | 410 → 338 | KEEP | Distractor 2/6 is exactly an HCF failure (divided by 2, not the highest common factor 4), and 411 already has the same edge at high confidence. |
| 4 | 426 → 425 | KEEP | 426 is 425 plus renaming both fractions; the easier case is the standard step before the general one, and without it 426 loses its path to equivalence errors. |
| 5 | 429 → 427 | KEEP | Adding the fraction parts of mixed numbers with unlike denominators is unlike-fraction addition, and 427 is the general case. |
| 6 | 434 → 433 | KEEP | Same reasoning as item 4 (subtraction mirror). It's also 434's only route to the equivalence error that distractor A tests. |
| 7 | 437 → 435 | KEEP | Same reasoning as item 5 (subtraction mirror); it's 437's only route to LCM and equivalence. |
| 8 | 3118 → 421 | KEEP | Reading a dash between labelled values builds directly on knowing that n equal gaps from 0 to 1 make n-ths, which is 421's skill. |
| 9 | 3193 → 164 | **DELETE** | 164 tests integer mental-division fluency, not division as sharing. A student failing 3 ÷ 4 = 3/4 has a conceptual gap, not a fluency gap, so the edge would blame the wrong skill. |
| 10 | 3241 → 432 | KEEP | Subtraction is how you solve a missing addend; 432 is the base of the subtraction chain. |
| 11 | 3328 → 432 | KEEP | Writing 2 as 8/4 and subtracting same-denominator fractions is a real step. |
| 12 | 3632 → 415 | **DELETE** | Comparing with 0, 1/2 or 1 is much easier than ordering arbitrary unlike fractions; 415 isn't needed for benchmark estimation, so the edge would blame the wrong skill. |

### Distractors (section 2)

| # | Question, option | Misconception | Decision | Reason |
| --- | --- | --- | --- | --- |
| 13 | q-3342-2 "2 1/9" | 14121 | OK | This misconception is tied to 3342 in Eedi's own data; a student unsure what "numerator" means can plausibly put the 2 as a whole part. |
| 14 | q-411-3 "3/7" | 22306 | **REMOVE** | It takes two steps (round, then simplify correctly); too contrived to be real evidence of the approximating misconception. |
| 15 | q-413-1 "5/9, 2/9, 7/9" | 18234 | OK | Keeping the first number first and ordering the rest is exactly what "first in the list is smallest" predicts. |
| 16 | q-3320-3 "You can't compare them without making the denominators the same" | 19731 | **REMOVE** | The option uses equivalence, the opposite of the tagged misconception, and it's arguably not false. A distractor that might be true is a bad distractor. |
| 17 | q-418-3 "2/3" | 15438 | OK | "Largest denominator means smallest" is the same belief as "smallest denominator means largest"; removing it would leave only 2 options. |
| 18 | q-414-3 "1/6, 1/12, 1/3" | 18234 | OK | Same pattern as 15. |
| 19 | q-3632-3 "-3/5" | 24501 | **REMOVE** | A subtraction-rule error in an estimation question, with a negative denominator; option C already covers students who calculate instead of estimating. |
| 20 | q-3839-1 "17 and 18" | 19360 | **REMOVE** | The error is plausible, but the tag (converting a mixed number to an improper fraction) is the wrong misconception, so evidence would go to the wrong node. |
| 21 | q-3839-2 "11 and 12" | 19360 | **REMOVE** | Same as 20. |
| 22 | q-3839-3 "23 and 24" | 19360 | **REMOVE** | Same as 20. |
| 23 | q-420-2 "2" | 18904 | OK | Generic, but the tag is accurate: 2 gaps for thirds is exactly "doesn't split into the correct number of parts". |
| 24 | q-435-1 "-1/2" | 24501 | OK | This is a subtraction question, so mechanically applying "subtract tops and bottoms" is believable here, unlike in 19. |
| 25 | q-3378-3 "288" | 22345 | **REMOVE** | Right error, wrong tag: a unit-rate word-problem misconception on bare division. |
| 26 | q-3193-3 "2" | 22991 | **REMOVE** | A real-life rounding misconception on a question with no real-life context, and the option isn't a fraction. |

### Spot checks (section 3)

| # | Question | Decision | Reason |
| --- | --- | --- | --- |
| 27 | q-428-1 | PASS | |
| 28 | q-415-2 | PASS | Close values, but correct, and the distractors are distinct errors. |
| 29 | q-434-1 | PASS | |
| 30 | q-425-2 | PASS | |
| 31 | q-434-2 | PASS | |
| 32 | q-3118-3 | PASS | C is exactly the error that makes a 0-to-2 scale hard. |
| 33 | q-417-1 | **FAIL** | B and C are logically the same statement, so a careful student can rule both out. **Fix:** remove option C "3/8 > 5/8" (22129). |
| 34 | q-420-1 | PASS | |
| 35 | q-3342-2 | PASS | Follows from item 13 being OK. |
| 36 | q-421-3 | PASS | |

### Known issues and future work (logged, no data change)
- **429 should probably also require 425** (item 5). Two of 429's three questions use the one-denominator-is-a-multiple case: q-429-2 (quarters and halves) and q-429-3 (thirds and sixths).
- **437 should probably also require 433** (item 7). Two of 437's three questions use the multiple case: q-437-1 (quarters and halves) and q-437-3 (thirds and sixths).
- **3241 should probably also require 433** (item 10). All three 3241 questions have different denominators, one a multiple of the other.
- **3328 is missing a negative-numbers prerequisite** (item 11). The skill (subtracting past zero) is outside the slice, and 3328's three distractors are all errors about crossing zero.

Regenerate after edits:
```
PYTHONPATH=api .venv/bin/python scripts/author_questions.py   # rewrites questions.json, fails on any bad question
make seed && make test
```

## 1. REQUIRES edges to check (12 of 59 are not "high")

Direction is (needs)-[:REQUIRES]->(prerequisite). If you delete an edge, also check `max depth` stays ≥ 3 (`tests/test_curated.py` checks it).

| Confidence | Construct (needs) | Prerequisite | Note |
| --- | --- | --- | --- |
| low | 3587 Understand comparing fractions is only valid when the two fractions refer to the same whole | 408 Identify equivalent fractions when presented as shapes or objects | Seeing that a fraction depends on its whole builds on fraction models of a shape; the link is indirect. |
| medium | 409 Identify equivalent fractions when presented as numbers | 408 Identify equivalent fractions when presented as shapes or objects | Numeric equivalence is normally taught after the same idea shown with shapes (concrete before abstract). |
| medium | 410 Simplify fractions that simplify to a unit fraction | 338 Identify the Highest Common Factor of two numbers | Simplifying to a unit fraction means dividing both parts by their highest common factor, which here is the numerator. |
| medium | 426 Add proper fractions with different denominators which share a common factor | 425 Add proper fractions with different denominators where one is a multiple of the other | This extends the one-denominator-is-a-multiple case to finding a new common denominator. |
| medium | 429 Add fractions involving mixed number fractions with different denominators | 427 Add proper fractions with different denominators which do not share a common factor | The fraction parts are added as unlike fractions; the coprime case is representative but depends on the denominators. |
| medium | 434 Subtract proper fractions with different denominators which share a common factor | 433 Subtract proper fractions with different denominators where one is a multiple of the other | This extends the one-denominator-is-a-multiple case to finding a new common denominator. |
| medium | 437 Subtract fractions involving mixed number fractions with different denominators | 435 Subtract proper fractions with different denominators which do not share a common factor | The fraction parts are subtracted as unlike fractions; the coprime case is representative but depends on the denominators. |
| medium | 3118 Read a fraction on a scale where the required number is marked by a dash between two numbers | 421 Represent positive non-unit fractions on a number line | Reading a dash between labelled values extends placing fractions on a number line. |
| medium | 3193 Express a division as a fraction | 164 Carry out mental divisions when the answer is an integer | Writing a ÷ b as a/b assumes the student understands division as equal sharing. |
| medium | 3241 Solve missing number fraction addition problems | 432 Subtract proper fractions with the same denominator | The missing addend is found by subtracting fractions (the inverse operation). |
| medium | 3328 Subtract with fractions and integers where the answer is less than 0 | 432 Subtract proper fractions with the same denominator | Subtracting an integer from a fraction is done by writing the integer over the same denominator and subtracting. |
| medium | 3632 Estimate the value of a fraction addition or subtraction using benchmark fractions | 415 Order fractions whose denominators are not multiples of the same number | Rounding to 0, 1/2 or 1 means comparing each fraction against those benchmarks. |

**Prerequisites chosen from outside Fractions (7):** 3378 times tables, 342 multiples, 345 LCM, 331 factors, 338 HCF, 164 mental division, 3193 division as a fraction. **Place value was left out on purpose:** I could not justify a REQUIRES edge from any of the four kept subtopics to a place-value construct in one sentence.

## 2. Distractors that are a stretch (14 options)

Each one names a real Eedi misconception with a SEEN_IN edge to the question's construct, but the wrong answer is not clearly what a student holding it would give. Fix the option, swap the misconception, or delete the option.

| Question | Option | Misconception | Why it is a stretch |
| --- | --- | --- | --- |
| q-3342-2: Which fraction has a numerator of 2 and a denominator of 9? | 2 1/9 | 14121 Uses numerator as whole part of a fraction | Uses the numerator as a whole-number part. |
| q-411-3: Simplify 14/35 fully. | 3/7 | 22306 Believes that simplifying a fraction involves approximating rather than finding an equivalent fraction with smaller terms | Approximates 14/35 as 15/35 and simplifies that. |
| q-413-1: Put these fractions in order from smallest to largest: 5/9,  | 5/9, 2/9, 7/9 | 18234 Thinks the first number in an unordered list must be the smallest | Assumes the first number in the list is the smallest. |
| q-3320-3: Which is true about 4/9 and 4/5? | You can't compare them without making the denominators the same | 19731 Does not realise that equivalence can be used to compare fractions | Does not see other ways (like equal numerators) to compare. |
| q-418-3: Which is the largest: 2/3, 7/12, 5/6? | 2/3 | 15438 Believes that a fraction with the largest denominator will be smallest regardless of the numerator | Ranks by denominator, so the smallest denominator is largest. |
| q-414-3: Put these fractions in order from smallest to largest: 1/6,  | 1/6, 1/12, 1/3 | 18234 Thinks the first number in an unordered list must be the smallest | Assumes the first number in the list is the smallest. |
| q-3632-3: Estimate 4/7 - 1/12 by rounding each fraction to 0, 1/2 or 1 | -3/5 | 24501 When subtracting fractions, believes you just subtract the numerators and subtract the denominators | Subtracts numerators and denominators: (4-1)/(7-12). |
| q-3839-1: Which two whole numbers does 17/5 lie between? | 17 and 18 | 19360 Thinks you replace the numerator with the number of wholes when converting a mixed number to an improper fraction | Reads the numerator as the number of wholes. |
| q-3839-2: Which two whole numbers does 11/4 lie between? | 11 and 12 | 19360 Thinks you replace the numerator with the number of wholes when converting a mixed number to an improper fraction | Reads the numerator as the number of wholes. |
| q-3839-3: Which two whole numbers does 23/6 lie between? | 23 and 24 | 19360 Thinks you replace the numerator with the number of wholes when converting a mixed number to an improper fraction | Reads the numerator as the number of wholes. |
| q-420-2: To mark 1/3 on a number line from 0 to 1, how many equal gap | 2 | 18904 Does not split number line into correct number of parts when representing fractions on it | Does not split the line into the right number of parts. |
| q-435-1: 2/3 - 1/5 = ? | -1/2 | 24501 When subtracting fractions, believes you just subtract the numerators and subtract the denominators | Subtracts numerators and denominators: (2-1)/(3-5) = 1/-2. |
| q-3378-3: 48 / 6 = ? | 288 | 22345 Believes that to find a unit rate, the total amount should be multiplied by the number of units, instead of divided | Multiplies instead of dividing. |
| q-3193-3: Which fraction is equal to 7 / 3? | 2 | 22991 Believes answers to real life problems should always be rounded to the nearest integer | Rounds the answer to the nearest whole number. |

Other things to look at in the same pass:
- **Construct 3839** (which two whole numbers a fraction lies between) has only 2 misconceptions in Eedi. All three "17 and 18"-style distractors are stretches; consider dropping that distractor and leaving 2-option questions.
- **Construct 3587** (comparing fractions needs the same whole) has only 1 misconception in Eedi, so its 3 questions have 2 options: q-3587-1, q-3587-2, q-3587-3.
- **31 questions have 3 options**, because the construct had too few misconceptions that map to a specific wrong answer: q-413-2, q-3320-1, q-3320-2, q-418-1, q-418-2, q-418-3, q-419-1, q-419-2, q-419-3, q-414-2, q-415-2, q-415-3, q-3839-1, q-3839-2, q-3839-3, q-420-2, q-430-1, q-430-2, q-430-3, q-426-1, q-426-2, q-426-3, q-3241-1, q-3241-2, q-3241-3, q-434-1, q-434-2, q-437-3, q-3378-1, q-3378-2, q-331-3.
- **Eedi data is noisy.** Some constructs list misconceptions from other topics (e.g. 437 lists "Believes number sequences always increase", 426 lists a probability misconception). I skipped those rather than force a distractor.

## 3. Ten random questions to spot-check (seed 12)

✅ = correct option. → shows the misconception id, its Eedi name, and the working that produces the wrong answer.

**q-428-1** (construct 428: Add fractions involving mixed number fractions with the same denominator)  
1 2/5 + 2 1/5 = ?
- A. 3 3/10 → 21651 "Believes that fractions are added by summing numerators and denominators as if they are separate whole numbers". _Adds numerators and adds denominators in the fraction part._
- B. 3 → 18151 "When adding mixed numbers believes they only need to add the integers". _Adds only the whole numbers._
- C. 3 3/5 ✅
- D. 2 2/25 → 26058 "Believes the integers are multiplied and the fractions of mixed numbers are multiplied rather than added when adding mixed numbers". _Multiplies the wholes (1 x 2) and multiplies the fractions._

**q-415-2** (construct 415: Order fractions whose denominators are not multiples of the same number)  
Which is the smallest: 2/3, 3/5, 5/8?
- A. 2/3 → 19420 "Believes smaller numerator means smaller fraction, regardless of denominator". _Picks the smallest numerator._
- B. 3/5 ✅
- C. 5/8 → 18665 "Believes larger denominator means smaller fraction, regardless of numerator". _Believes a larger denominator means a smaller fraction._

**q-434-1** (construct 434: Subtract proper fractions with different denominators which share a common factor)  
5/6 - 3/4 = ?
- A. 2/12 → 26989 "Believes numerators stay the same when finding common denominators". _Changes the denominators to 12 but not the numerators._
- B. 1/12 ✅
- C. 2/2 → 24501 "When subtracting fractions, believes you just subtract the numerators and subtract the denominators". _Subtracts numerators and denominators: (5-3)/(6-4)._

**q-425-2** (construct 425: Add proper fractions with different denominators where one is a multiple of the other)  
2/3 + 1/6 = ?
- A. 5/6 ✅
- B. 3/6 → 26985 "Believes the denominator of the result is always the larger denominator when adding or subtracting fractions". _Adds the numerators and uses the larger denominator._
- C. 3/3 → 26161 "Believes the denominator of the result is always the smaller denominator when adding or subtracting fractions". _Adds the numerators and uses the smaller denominator._
- D. 3/9 → 15521 "Believes adding the denominators gives a common denominator". _Adds the denominators to get a common denominator._

**q-434-2** (construct 434: Subtract proper fractions with different denominators which share a common factor)  
7/10 - 1/4 = ?
- A. 6/6 → 24501 "When subtracting fractions, believes you just subtract the numerators and subtract the denominators". _Subtracts numerators and denominators: (7-1)/(10-4)._
- B. 9/20 ✅
- C. 6/20 → 26989 "Believes numerators stay the same when finding common denominators". _Changes the denominators to 20 but not the numerators._

**q-3118-3** (construct 3118: Read a fraction on a scale where the required number is marked by a dash between two numbers)  
A number line goes from 0 to 2. It is split into 8 equal gaps by 7 dashes. An arrow points to the 3rd dash after 0. What number is at the arrow?
- A. 3 → 18486 "Believes each dash on a decimal number line represents 1". _Treats each dash as worth 1._
- B. 3/4 ✅
- C. 3/8 → 15358 "Assumes a fractional scale will only go from 0 to 1". _Assumes a fraction scale only goes from 0 to 1._
- D. 3/7 → 15999 "When reading a dash on a number line counts 1 dash too few when working out the divisions". _Counts the 7 dashes as the divisions, one too few._

**q-417-1** (construct 417: Use inequality notation to order fractions with the same denominators)  
Compare 5/8 and 3/8. Which statement is true?
- A. 5/8 > 3/8 ✅
- B. 5/8 < 3/8 → 18657 "Believes smaller numerator means larger fraction when denominators are equal". _Believes a smaller numerator means a larger fraction._
- C. 3/8 > 5/8 → 22129 "Confuses greater than and less than symbols". _Confuses the greater than and less than symbols._
- D. 5/8 = 3/8 → 14089 "Believes that fractions with the same denominator are equal". _Believes fractions with the same denominator are equal._

**q-420-1** (construct 420: Represent positive unit fractions on a number line)  
A number line from 0 to 1 is split into 5 equal gaps. What fraction is at the first dash after 0?
- A. 1 → 18349 "Believes the first mark on a number line is always 1". _Believes the first mark on a number line is always 1._
- B. 1/5 ✅
- C. 1/6 → 15304 "When finding the difference between two marks on a scale, counts lines instead of gaps". _Counts the 6 marks (lines) instead of the 5 gaps._
- D. 0.5 → 26288 "Believes a fraction can be converted to a place value representation by writing the digits of the denominator directly after the decimal point, ignoring the numerator". _Writes the denominator after the decimal point: 1/5 = 0.5._

**q-3342-2** (construct 3342: Read fractions)  
Which fraction has a numerator of 2 and a denominator of 9?
- A. 2 1/9 → 14121 "Uses numerator as whole part of a fraction". _Uses the numerator as a whole-number part._ ⚠️ stretch
- B. 9/2 → 16784 "Believes the denominator is the top of a fraction". _Thinks the denominator goes on top._
- C. 2/9 ✅
- D. 29 → 14014 "Does not know how to write a fraction - just given an integer answer". _Writes the numbers side by side as an integer._

**q-421-3** (construct 421: Represent positive non-unit fractions on a number line)  
A number line from 0 to 1 is split into 10 equal gaps. An arrow points to the 7th dash after 0. Which fraction is at the arrow?
- A. 7/11 → 15304 "When finding the difference between two marks on a scale, counts lines instead of gaps". _Counts the 11 marks (lines) instead of the 10 gaps._
- B. 7/10 ✅
- C. 10/7 → 18297 "Believes that x/y is equivalent to y/x in all cases". _Believes x/y is the same as y/x._
- D. 1/7 → 18805 "When asked for a fraction on a number line, assumes it is a unit fraction with the number of dashes up to the required fraction as a denominator". _Assumes a unit fraction with the dash count (7) as the denominator._

## 4. Deviations from SPEC.md

**Query changes for FalkorDB v4.20.7**
1. `ROOT_CAUSE_CHAIN`: `ORDER BY length(p)` fails on an unprojected path ("Unable to locate a value with alias p"). It now returns `length(p) AS hops` and orders by `hops`. Same intent.
2. All other SPEC queries ran unchanged: `REQUIRES*0..6` (includes the target at depth 0), the NOT pattern predicates in `next_question`/`probe_frontier`, `algo.SPpaths`, `algo.WCC`, `algo.pageRank`, `algo.betweenness` (deterministic with the seed), `CLAIM`.
3. **Vector score is a cosine distance** (the exact text scores 0.0), so the SPEC's `ORDER BY score ASC` is correct and was not changed.

**Verified on v4.20.7**
- `GRAPH.COPY` carries all 9 indexes, including the vector index, into `class_demo`. Query plans use them. `05_new_class.py` still checks and would recreate any that went missing.
- `claim` is race-safe: 20 rounds of 10 concurrent claims, exactly one winner each time.

**Additions beyond the SPEC**
4. **Receipts:** `cypher` and `params` are lists, one entry per query the tool ran (e.g. `root_cause` runs 2, `record_attempt` runs 3–4). `node_ids` is a list of `{label, id}`, because Construct and Misconception ids are both integers and could collide.
5. **Helper queries/functions that are not among the 16 tools:**
   - `start_session`, `log_event` (episodic memory)
   - `create_task` (`handoff` needs a previous task)
   - `MASTERY_EVIDENCE` / `MARK_MASTERED` (the SPEC's Python mastery rule)
   - `QUESTION_OPTIONS`, `SKILL_BY_NAME`, `SET_PAGERANK`, and the loader and test-count queries
6. **`record_attempt` also marks MASTERED** (2 correct answers on the construct, no SHOWED above 0.6) in the same call.
7. **`learning_path` takes an optional `to_id`** to run the `algo.SPpaths` shortest chain. **`keystones` writes `pagerank` back only for the top 10** it returns.
8. **`propose`** enforces the allowlist (`regroup`, `skip_ahead`, `assign_practice`) in Python and JSON-encodes the payload. **`decide`** accepts only `approved`/`rejected`.

**Data and loader choices**
9. **Extra columns and fields:**
   - `requires.csv` has a `confidence` column (as you asked). REQUIRES edges also store `note` and `confidence` alongside `source:'curated'` and `weight:1`.
   - `questions.json` options carry extra fields: `check` (the maths spec used to verify the question), `why` and `stretch`. The graph stores only the SPEC fields.
10. **Questions have 2–4 options**, not always 4 (see section 2).
11. **8 skills**, two of them not in the SPEC's list: "Same-size pieces comparison" and "Factor and multiple ladders". Skills also store a `description`.
12. **`04_build_template.py` deletes and rebuilds `class_template`** on every run (idempotent by rebuild). It reads the slice out of `curriculum` with Cypher, so the template comes from the graph, not the CSVs.
    - It **fails the build** on any question option whose misconception has no SEEN_IN edge to the question's construct, rather than silently dropping it.
13. **Embeddings** are normalised MiniLM vectors, written 100 rows per batch instead of 500 (384 floats per row makes 500-row query strings about 2 MB).
14. **Extra range indexes** on Subject/Topic/SubTopic `id` (from Phase 1). Students are `s01`–`s30` with synthetic first names.

## 5. Things to watch later
- **Shared misconceptions spread evidence.** *Fixed in Phase 3 step 0: `root_cause` now weights each hit by `SEEN_IN.pct / 100`, tested in `tests/test_root_cause_weighting.py`; Diagnoser thresholds rescaled to 1.0 / 0.33.* Original note: `root_cause` counts SHOWED evidence on every construct a misconception is SEEN_IN. Generic ones like 13957 "Confuses factors and multiples" are SEEN_IN 342, 345, 331 and 338 at once, so one wrong answer adds evidence to all four.
- **`diagnose_text` can return fewer than 3 rows.** It over-fetches 25 of the 410 template misconceptions, then filters to the construct, so constructs with only a few misconceptions may come back short.
- **The image's default `TIMEOUT 1000`** (from Phase 1) is far from being hit. The slowest tool, `bridges`, runs at p95 41 ms. Every class-graph tool is under 5 ms p95 (measured in Phase 3, table in section 6).

## 6. Phase 3 review items

### Latency (measured, `eval/results/latency.json`)
Setup:
- 50 calls per tool after 3 warm-ups, on `class_demo` (30 students).
- Before timing, every student ran one simulated session (seed 0), so the reads see real SHOWED/ATTEMPTED state.
- Timing is wall clock around the Python tool function, so it includes the localhost round trip and building the receipt.
- FalkorDB v4.20.7 in Docker on macOS.
- `class_demo` was rebuilt clean afterwards.

| Tool | p50 ms | p95 ms |
| --- | ---: | ---: |
| `record_attempt` | 1.22 | 1.69 |
| `diagnose_text` | 3.89 | 4.63 |
| `next_question` | 0.45 | 0.92 |
| `root_cause` | 0.97 | 1.10 |
| `probe_frontier` | 0.59 | 0.70 |
| `learning_path` | 0.68 | 0.75 |
| `recall` | 0.40 | 0.48 |
| `pick_skill` | 0.67 | 0.75 |
| `update_skill` | 0.59 | 0.65 |
| `cohorts` | 1.67 | 1.81 |
| `keystones` | 0.81 | 0.96 |
| `bridges` | 35.87 | 40.89 |
| `claim` | 0.38 | 0.50 |
| `handoff` | 0.33 | 0.39 |
| `propose` | 0.33 | 0.36 |
| `decide` | 1.09 | 1.20 |

- `diagnose_text` includes embedding the explanation on CPU.
- `bridges` runs betweenness on the full curriculum graph.
- `decide` was measured on approved `assign_practice`, so it includes the executor and its Event.

### The Diagnoser does not probe deepest-first (deviation, please confirm)
The SPEC's loop probes `probe_frontier`'s deepest unprobed prerequisites first. On the simulator (seed 0, 30 students) that got the planted root top-1 in **8/30** (top-3 16/30). Targets have up to 9 prerequisites, roots are usually 1–2 hops down, and the 6-question budget went on deep constructs the student already knew.

The Diagnoser now searches top-down using `learning_path` rows:
- It asks about the closest unasked prerequisite first.
- A correct answer rules out that construct and everything it depends on.
- A wrong answer makes it a suspect, and the search continues below it.
- It confirms the deepest suspect before stopping.

`probe_frontier` is kept as the fallback. All tools and queries are unchanged.

Results, top-1 (top-3) over 30 students:

| Policy | Seed 0 | Seed 1 | Seed 2 |
| --- | --- | --- | --- |
| SPEC deepest-first | 8/30 (16/30) | — | — |
| Top-down search | 17/30 (27/30) | 23/30 (27/30) | 19/30 (25/30) |

This is an informal check, not the eval harness. The SPEC deepest-first policy was only measured on seed 0.

### `pct` weighting makes roots with generic misconceptions hard to find (decision needed)
Step 0's evidence formula weights each hit by `SEEN_IN.pct / 100`. It does what you asked: in `tests/test_root_cause_weighting.py`, a specific misconception beats a generic one spread over 4 prerequisites.

But some prerequisites only have generic Eedi misconceptions:
- 3342 (fraction notation): its distractors' `pct` values are 25, 21, 20, 10, 5.9 and 1.5.
- 3378 (times tables): mostly under 6, except two (100 and 50).

Two hits on 3342 score at most 0.375, while one hit on a construct that depends on it, with a `pct` 100 misconception, scores 0.5. So `root_cause` ranks the dependant first.

With a noiseless simulated student (every answer follows the planted state), across every planted (root, target ≥2 hops) pair:
- 3342 was found 1/24 times.
- 3378 was found 8/19 times.
- Every other root was found 46/49 times.

Options, none applied yet:
- (a) Normalise `pct` within the class slice (divide by the misconception's total `pct` over the slice's constructs).
- (b) Normalise per construct (divide by the construct's highest distractor `pct`).
- (c) Keep the formula and rank by depth among candidates above an evidence floor.

I'd try (a) first: it keeps your "generic spread counts less" property, and it stops penalising constructs whose misconceptions also appear outside the slice.

### Other Phase 3 deviations and choices
15. **Task carries `construct_id` and `session`.** The SPEC's Task has neither, but every agent needs both.
    - `CREATE_TASK` sets them.
    - `HANDOFF` copies them from `prev` in the same write. A follow-up query would leave a window where a worker claims a task that has no context yet.
16. **`COHORTS_WCC` also returns `ids`** next to the aliases, so the Teacher can propose for those students.
17. **`pick_skill` also returns the skill's `steps`** (`SKILL_STEPS`).
18. **`propose` validates the payload:**
    - `regroup` needs 2 or more students.
    - `skip_ahead` and `assign_practice` need an integer `construct_id`.
19. **The approval executor reads its targets from the graph.** It uses the Proposal's `FOR` edges, not the caller's payload.
    - `regroup` creates `(:Group)-[:HAS_MEMBER]->(:Student)`.
    - `skip_ahead` creates `MASTERED {evidence:'teacher_override'}`, ON CREATE only, so an earned MASTERED is never overwritten.
    - `assign_practice` creates `(:Assignment)-[:FOR]->(:Student)` and `-[:PRACTICES]->(:Construct)`.
    - The Event hangs off the Proposal (`(:Proposal)-[:HAD_EVENT]->(:Event)`), since no student Session is involved.
    - Reject sets state only.
20. **Tutor escalation rule.** `SHOWED` confidence never drops, so "confidence stays > 0.6" would escalate everyone. The Tutor hands off to the Teacher when the check answer is **wrong** and the root's top misconception confidence is above 0.6. Otherwise the chain ends at the Tutor.
21. **Teacher agent choice.**
    - It proposes `regroup` when the student is in a WCC cohort, otherwise `assign_practice` on the student's root cause.
    - It never proposes `skip_ahead` from a review task (that kind is allowed through MCP and tested).
    - It also runs `root_cause` to get the construct for the payload; the SPEC lists only cohorts, keystones and bridges.
22. **LLM receipt check.**
    - The model must wrap names in `[[...]]`. Each marked name must be a value in that turn's tool rows.
    - Any known construct or misconception name of 15+ characters that appears unmarked must be in the rows too. A substring of a row value counts.
    - Invented names that are neither marked nor in the vocabulary can't be caught by any deterministic check. The template is the backstop.
23. **LLM models** (checked against each provider's docs on 2026-10-17):
    - Groq `llama-3.3-70b-versatile`.
    - Gemini `gemini-3.8-flash`.
    - OpenRouter `google/gemma-4-31b-it:free`. OpenRouter lists no free Llama 70B model now.
    - Free-tier rate limits aren't on Groq's or Google's public pages; they only appear in each account's console.
    - **`.env` has no API keys, so no live provider call has been made.** Everything so far, demo included, ran in template mode.
24. **`mcp==1.30.0`, not 2.x.** mcp 2.x renamed `FastMCP` to `MCPServer`. 1.30.0 runs the SPEC's code as written. `openai==3.24.0` (newest release at least two weeks old).
25. **`.env` is loaded by repo path** in `db.py` and `llm.py`, so the MCP server works from any working directory (the test starts it from `/`).
26. **Demo helpers:** `reset_student` (session 1 of `demo_session.py` replays from scratch), `sessions`, `chain`, `proposals`, `showed_on` and `name_vocabulary`. All their Cypher is in `queries.py`.
27. **The simulator reads the curated files, not the graph.** It is the ground truth, so it must not share the agents' queries. It has a `noiseless` mode used only by the end-to-end tests.
28. **Tutor check question:** it asks on the root cause if a question is left. Otherwise it asks on the closest construct above the root on the `root_cause` chain, which depends on the root.

### Questions run out across sessions (decision needed)
`next_question` excludes every question the student has ever attempted (`NOT (s)-[:ATTEMPTED]->(q)`). With 3 questions per construct, session 1 often uses all of the root's questions. Session 2 then can't re-ask the root. It opens with recall as it should, but its diagnosis and check question land on other constructs: in the s18 transcript, 408 has nothing left in session 2.

Options:
- (a) Exclude only questions attempted in the current session. This is a one-clause change to the SPEC query: `NOT (s)-[:ATTEMPTED {session:$sess}]->(q)`.
- (b) Author 5 questions for the constructs that are often roots.
- (c) Accept it for the demo, since session 2's job is recall.
