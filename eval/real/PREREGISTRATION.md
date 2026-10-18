# Pre-registration: Unlearn on real student data (Eedi NeurIPS 2020)

> **Primary hypothesis (single, Deviation 5).** Task A, **M2 vs M2-nograph**, AUC, 9-edge graph, all test students: do the prerequisite edges improve next-answer prediction?
> **Key secondary:** the same comparison on each student's first 2 quizzes (cold start).
> **Everything else is secondary or exploratory:** the M0, M0b, M1 and M3 comparisons, the 12-edge sensitivity graph, and all of Task B.

Written and committed before any model is run on the test students. After the test run, nothing below changes. Anything that has to change is added under **Deviations**, dated, with the reason, and both versions are reported.

- Drafted by Claude Code. Decisions marked *(Parth)* are Parth's, from Phase 0 and the edge review on 2026-10-18. The other design details (M2's features, BKT's EM start, M3's β grid, the Task B D/N rules) are Claude's proposals, shown to Parth before the test run.
- Data, licence and download: [DATA.md](DATA.md). Edge review: [EDGE_REVIEW.md](EDGE_REVIEW.md).

## 1. Question

Does the structure of Unlearn's prerequisite graph carry signal on real students?

This tests a **reduced** version of Unlearn. The real data has no question text and no option-to-misconception labels, and it is tagged only down to SubTopic. So the graph model here is named **"M2: graph-structure prior, correctness-only"** in every output. It is **not** a test of Unlearn's misconception reasoning, and results must not be described as one.

## 2. Data (fixed)

- **Source:** Eedi NeurIPS 2020, Tasks 1–2 data. Train and test answer files pooled, joined to `answer_metadata` on AnswerId (`data.py`).
- **Questions:** those whose Level-3 SubjectIds include exactly one of our 7 SubTopics {204, 219, 220, 226, 227, 228, 230}: 2,420 questions. 59 tagged with more than one of ours are dropped.
- **Students:** 10 or more answers on those questions: **50,247 students, 1,622,755 answers**.
- **Split:** by student, never by row. The sorted UserIds are permuted with `numpy.random.default_rng(0)`; the first 20% are test.
  - Train: 40,198 students, 1,296,571 answers.
  - Test: 10,049 students, 326,184 answers.
- **Time:** `ts` = DateAnswered (minute resolution).
  - A **block** is one (UserId, QuizId, ts).
  - Every answer is predicted from the student's answers with a strictly earlier `ts` only. Answers in the same block never see each other, nor do two blocks of one student with the same `ts`.
  - The same rule applies when fitting on train students.
  - Within one `ts`, updates are applied in AnswerId order. AnswerId is not time-ordered (Spearman −0.0), so this order is arbitrary but fixed, and it only affects state after the block.
- **Quizzes:** a student's quizzes are ordered by their first `ts`, then QuizId. "First 2 quizzes" means quiz ranks 0 and 1.

## 3. Graph (fixed, *Parth*)

- **Primary:** the 9 edges kept in the edge review (`subtopic_edges.csv`, `decision = keep`). Acyclic, asserted in a test.
- **Sensitivity:** the original 13 collapsed edges minus edge 4 (226 → 227): 12 edges, acyclic. M2, M3 and Task B are also run on it. The 9-edge graph is primary; both are reported.
- **Walk:** prerequisites within 1–4 hops, as in `ROOT_CAUSE` (`REQUIRES*1..4`), with depth = the minimum hop count.

## 4. Correctness-only evidence (deviation from production, by design, *Parth*)

Production evidence is `SHOWED.count × SHOWED.confidence × SEEN_IN.w`, summed over a construct's misconceptions. The real data has no misconceptions, so each SubTopic gets one stand-in "misconception":

- A **wrong answer on SubTopic X** increments `wrong[X]`, with weight w = 1.
- **Confidence** at X = `1 − 0.5^wrong[X]` (production `UPDATE_SHOWED`).
- **Evidence** at X = `wrong[X] × (1 − 0.5^wrong[X])`.
- **Mastered** X: the first time `right[X] ≥ 2` (production `MASTERY_CORRECT`) while confidence at X ≤ 0.6 (`MASTERY_MAX_CONFIDENCE`). Mastery is permanent (MERGE, never removed), as in production.
- **root_cause(target T):** the prerequisites P of T within 1–4 hops that are not mastered and have evidence > 0. They are ordered by evidence descending, then depth descending (production `ROOT_CAUSE`); the top row is the diagnosis (production Diagnoser).
- **confident:** top evidence ≥ 1.5 and a lead over the runner-up ≥ 0.5 (production `EVIDENCE_MIN`, `LEAD_MIN`).
- **No re-tuning:** the constants are imported from `unlearn.tools` and `unlearn.agents.diagnoser`, not copied.
- **Cross-check:** a test checks that the Python implementation returns the same rows as the production `ROOT_CAUSE` Cypher on FalkorDB, for random histories on the SubTopic graph.

## 5. Task A: next-answer prediction (main result)

Each model outputs P(correct) for every test answer. Every parameter is fitted on train students only.

| Model | Definition |
| --- | --- |
| **M0** question difficulty | (train correct + 1) / (train answers + 2) for the question; questions unseen in train get the train correct rate. |
| **M0b** running accuracy | (student's earlier right on X + 2·p_X) / (earlier answers on X + 2), where p_X is the train correct rate on SubTopic X, so a student with no history on X gets p_X. |
| **M1** BKT per SubTopic | Plain 4-parameter BKT (P(L0), P(T), P(S), P(G)) per SubTopic, no forgetting, fitted by EM (Baum–Welch) on the train students' sequences on X. EM starts at (0.4, 0.1, 0.1, 0.2), with guess and slip capped at 0.5 (Deviation 7), and stops at 200 iterations or a log-likelihood change < 1e-6. Prediction: P(L)(1−S) + (1−P(L))G, with P(L) after the student's earlier blocks on X. Implemented here, see Deviation 1. |
| **M2** graph-structure prior, correctness-only | Logistic regression (scikit-learn, L2, C = 1.0, lbfgs) fitted on the train students. Features at prediction time: logit(M0), evidence at X, mastered X (0/1), and **prerequisite suspicion** = the top evidence of root_cause(X) (0 if none). |
| **M2-nograph** (ablation) | M2 without prerequisite suspicion: logit(M0), evidence at X, mastered X. M2 vs M2-nograph is the cleanest test of the graph edges, since it is the only difference between them. |
| **M3** BKT + graph prior | M1, except that the student's P(L0) for X at their first block on X is P(L0)_X · exp(−β · prerequisite suspicion at that time). β is chosen from {0, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2} by train-student predictive log-likelihood. |

**Metrics** (on all test answers):
- **Primary:** AUC.
- **Secondary:**
  - log-loss (probabilities clipped to [1e-6, 1 − 1e-6]);
  - accuracy (threshold 0.5);
  - AUC on each student's first 2 quizzes (cold start) and on later quizzes.

**Uncertainty:**
- 95% percentile intervals from 1,000 resamples of the test students with replacement (seed 0). AUC is recomputed on all answers of the resampled students.
- Differences between models are paired: the same resamples are used for both models.

**Pre-registered comparisons** (all reported whatever they show; A2 on all test students is the single primary hypothesis and A2 on the first 2 quizzes the key secondary, the rest secondary, Deviation 5):
- **A1:** M2 − M1 AUC (does it beat BKT).
- **A2:** M2 − M2-nograph AUC (do the graph edges add anything).
- **A3:** A2 on the first 2 quizzes vs on later quizzes (the graph should help most at cold start).
- **A4:** M3 − M1 AUC.
- Also reported, without hypotheses: M0, M0b and M1 side by side.

**Success criteria:**
- **"Better":** a difference whose 95% interval excludes 0 **and** whose point estimate is ≥ 0.005 AUC.
- **"No detectable difference":** the interval includes 0.
- **"Negligible":** the interval excludes 0 but the point estimate is < 0.005.
- If BKT (or anything else) beats M2, that is reported as the result.

## 6. Task B: is the diagnosed root real? (exploratory, Deviation 6)

For each test student and k ∈ {5, 10}:

1. **Window:** the student's first quizzes in order, until the cumulative answers reach ≥ k.
2. **Later:** answers in the remaining quizzes with `ts` after the window's last `ts`.
3. **Diagnosis:**
   - Targets are the SubTopics with ≥ 1 wrong answer in the window.
   - root_cause (section 4) runs on the window's state for each target; the rows are pooled across targets.
   - The root is the row with the most evidence, then the greatest depth, then the lowest SubTopic id.
   - No row means the student has no diagnosis.
4. **Sets:**
   - D = the SubTopics that depend on the root (it is their prerequisite within 1–4 hops).
   - N = the other SubTopics.
   - The root's own SubTopic is excluded from both.
5. **Lift:** a student is evaluable if they have ≥ 1 later answer in D and ≥ 1 in N. For each evaluable student, lift = error rate on later answers in D − error rate on later answers in N. The reported number is the mean over evaluable students, with a student-bootstrap interval (1,000, seed 0).

**Comparison roots**, computed for the same students with the same D/N rule:
- **random:** uniform over the roots Unlearn can be evaluated on: the SubTopics that have dependents, minus 204 (N is empty for 204). That is {219, 220, 226} in the primary graph and {219, 220, 226, 227} in the sensitivity graph (Deviation 8). One draw per student, `default_rng(0)`, in sorted UserId order.
- **BKT lowest mastery:** among the root candidates, the lowest M1 P(L) after the window (P(L0) where unobserved); ties go to the lowest id.

**Reporting:**
- Each method's lift; paired differences Unlearn − random and Unlearn − BKT.
- The number of evaluable students, and how many diagnoses fall at each root.
- A diagnosis at 204 is never evaluable in the primary graph, because everything depends on 204 and N is empty. The count of those students is reported.

**Secondary:**
- Difficulty-adjusted lift: the same, using residuals (1 − correct) − (1 − M0) instead of raw error. This removes question difficulty, because D SubTopics may simply be harder.
- The lift restricted to students whose diagnosis is `confident`.

**Power:** if fewer than **500** test students are evaluable for a given k and graph, Task B is reported as **underpowered** for that cell, and no claim is made from it.

**Success criterion:** the root is "real" if Unlearn − random lift has a 95% interval above 0. Unlearn − BKT is reported alongside. Task B is exploratory (Deviation 6): it supports no headline claim.

## 7. Task C: dropped (*Parth*)

Predicting which wrong option a student picks next needs wrong options linked to misconceptions, together with student responses. Phase 0 found no public source with both:
- **NeurIPS 2020:** has the chosen option (AnswerValue) but no misconception labels. Its questions exist only as images, which can't be used, and its anonymised question IDs can't be matched to other Eedi releases.
- **Eedi Misconceptions Graph:** misconception ↔ construct only.
- **Kaggle "Eedi – Mining Misconceptions in Mathematics":** has option labels but no student responses.

## 8. Procedure

1. All code is developed and debugged on train students only.
2. Leakage tests pass, for every model:
   - Every prediction uses only answers with an earlier `ts`.
   - Changing the outcomes of a student's answers with `ts` ≥ t leaves every prediction for that student's answers with `ts` ≤ t unchanged, including the other answers in the same block.
3. The BKT unit test passes, against a hand-computed example.
4. `make real-eval` runs once on the test students. It writes `eval/results/real/*.json` (aggregates only, with the git commit hash) and `RESULTS.md` tables.
5. Results are reported as they come, including null and negative ones.

## 9. Deviations

1. **2026-10-18, before any test run: pyBKT not used.** pyBKT 1.4.3 installs but fails on import with scikit-learn 1.9.1: at import time its `metrics.py` calls `log_loss` with a plain Python list, which sklearn 1.9 rejects (`'list' object has no attribute 'dtype'`). Downgrading sklearn would change the app's environment, so pyBKT was uninstalled and M1 is plain BKT (section 5), unit-tested against a hand-computed example (Parth's decision).
2. **2026-10-18, before any test run: correctness-only evidence** (section 4), instead of misconception evidence, because the data has no misconception labels (Parth's decision).
3. **2026-10-18, before any test run: SubTopic granularity** (section 3), instead of our 40 constructs, because questions are tagged only to SubTopic and their text is only in images that can't be used (Parth's decision).
4. **2026-10-18, before any test run: the cold-start split** is the first 2 quizzes rather than the first 5 answers (Parth's decision). Most quizzes are answered within one minute, so answer counts within a quiz carry no time order.
5. **2026-10-18, before any test data is touched: a single primary hypothesis** (Parth's decision). Task A, M2 vs M2-nograph, AUC, 9-edge graph, all test students. Key secondary: the same comparison on each student's first 2 quizzes. All other comparisons (M0, M0b, M1, M3, the 12-edge graph) and Task B are secondary or exploratory. Previously A1–A4 were listed without a primary.
6. **2026-10-18, before any test data is touched: Task B is exploratory** (Parth's decision). It keeps exactly the design in section 6. Cells under 500 evaluable students are reported as underpowered, with no threshold or graph changes to gain power. **What the dev run showed:** the dev run (train students only, 8,040 held-out train students, `--dev`) computed and printed full tables for both tasks: Task A AUCs, including M2 vs M2-nograph, and Task B lift values. Claude saw them, including a check of the report script on the dev output. The message to Parth reported only Task B counts (diagnosed and evaluable students per cell) and the BKT fit ranges, no Task A or Task B metric values. Deviations 5–8 were decided by Parth after that message.
7. **2026-10-18, before any test data is touched: BKT guess and slip capped at 0.5** (Parth's decision), the standard identifiability constraint, so that "learned" never means worse. Applied in the EM M-step (`models.fit_bkt`). The dev fits already satisfied it: guess 0.386–0.485, slip 0.107–0.166 across the 7 SubTopics.
8. **2026-10-18, before any test data is touched: Task B's random root comes from Unlearn's evaluable roots** (Parth's decision): the SubTopics with dependents minus 204, so the comparison is like-for-like. BKT's lowest-mastery root is unchanged (all root candidates, 204 included).
