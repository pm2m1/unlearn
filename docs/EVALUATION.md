# Evaluation

[Back to the README](../README.md)

# Evaluation

**Method** (`eval/run_eval.py`, per the build spec):
- **Students:** 30 simulated students × 3 seeds × 2 sessions. All the data is synthetic: the students, their answers and their planted misconceptions.
- **Planted state:** each student has one planted broken prerequisite and 1–3 planted misconceptions.
- **Simulator:** rule-based and seeded (`eval/simulator.py`).
  - If an option shows a planted misconception, the student picks it with probability 0.85.
  - On skills the student knows, they answer correctly with probability 0.9.
  - Otherwise they pick a random wrong option.
  - There is a 10% guess rate everywhere.
- **Conditions:**
  - **A: no memory.** One LLM call per wrong answer. It sees only that question and the misconceptions retrieved for it.
  - **B: vector RAG.** The full attempt history, plus the top-10 misconceptions retrieved from FalkorDB's vector index by embedding each question with the chosen option.
  - **B+: LLM + graph as text.** B's prompt, plus every curated `REQUIRES` edge and every construct's misconceptions with their `SEEN_IN.w` weights, as plain text (about 22,000 tokens). B+ tests whether the graph's value is the *knowledge* in it, which can be pasted into a prompt, or the *traversal* Unlearn runs over it.
  - **C: Unlearn.** The agents, through the same step API the web UI uses.
- **Same model throughout.** A, B and B+ use one local model with no fallback: `qwen3.5:27b-q4_K_M` through Ollama, thinking off. Replies are cached on disk. Cached diagnoses, and A's diagnoses that made no call (a student with no wrong answer), are left out of the latency figures. On the post-review re-run most A and B diagnoses were cache hits (A had 5 fresh diagnoses, B 30), so A's, B's and B+'s latency pools every timed diagnosis from the pre-review and post-review runs (`run_eval.py --pool-latency`). Each fresh call is timed once, in the run that made it. Every latency cell shows its n.
- **Same question pool.** A, B and B+ ask the same seeded 6 questions from the pool C draws from (the target and everything it depends on). C chooses its questions adaptively.
- **Answers are IDs.** A, B and B+ choose from candidate lists with IDs and must reply with IDs. An ID the condition wasn't shown counts as wrong.
  - Root-cause candidates are the target's prerequisites, taken from the curated graph. **That narrows their choice to about 7 skills and favours them.** A random pick is already right 21–24% of the time.
  - Misconception candidates are the retrieved ones for A and B. B+ is scored on every ID it was shown: B's lists plus every misconception and construct in its graph text.
- **Session-2 recall** means the opening message of session 2 names a planted misconception, as judged by embedding distance ≤ 0.35 for every condition. B+ opens exactly as B does, so the two share a recall score.
- **The first run's scoring was replaced** (pre-review data). It asked for free text and snapped every answer to its nearest ID, so a vague answer was still scored as a specific skill. An audit of its cached outputs found no invalid JSON, but 8–14 of about 30 root-cause guesses per condition and seed weren't close to the skill they were scored as. Scoring by offered IDs roughly doubled A's and B's root-cause scores on seed 0 (13% → 27% and 10% → 27%).
- **B+ ran on seed 0 only.** At about 110 s per call, all three seeds would have taken nearly three hours (163 minutes projected), against a 75-minute budget.
- **Correction (Oct 18, pre-review data): B+ re-scored.** B+ was first scored only on IDs from B's retrieved list, although its prompt lists all 410 misconceptions with their IDs. Planted misconceptions it named from the graph text were counted wrong. It was re-scored on every ID it was shown, from the cached model outputs with no new LLM calls (`eval/rescore_bplus.py`). The replay reproduced A's and B's saved predictions exactly, and only B+'s scoring fields changed (14 of 30 students). Results:
  - Top-1 misconception went from 10% to 17%.
  - Top-3 misconception went from 20% to 33%.
  - Root cause stayed at 37%: every planted root is one of the prerequisites B+ was offered anyway.
  - A, B, C, latency and recall are unchanged.
- **Re-run after the human review (Oct 18).** Parth's review of the curated data ([REVIEW.md](../REVIEW.md), section 0) deleted 2 `REQUIRES` edges and removed 9 options. Every condition was then re-run on the new data with the same seeds, so all the numbers below are post-review. The simulator draws each student's planted state from the graph, so 14 of the 90 students have a different planted root or misconceptions than before; within the run, every condition still faces the same students. The pre-review run is kept in [`eval/results/eval_pre_review.json`](../eval/results/eval_pre_review.json).
- **Oct 19: recall 57% → 58% after re-run; the earlier number predated an Oct 18 wording fix. Noise table re-run from current code.**
  - Every condition, every seed, the noise test, the random baseline and the design checks were re-run from the same code with the same seeds. A, B and B+ were served entirely from the reply cache, so their numbers are unchanged and they timed no new calls; their latency still pools the earlier runs (the Oct 18 run is kept as [`eval_oct18_post_review.json`](../eval/results/eval_oct18_post_review.json)).
  - The only number that moved apart from wall-clock latency is C's session-2 recall: 57% → 58% over seeds 0–2, 50% → 53% on seed 0, and the noise test's p = 0 recall 59% → 58%. Nothing else moved: every other accuracy, interval, random-baseline and design-check number is identical.
  - Why: the main eval ran before the Oct 18 wording fix to the session-2 opening ("1 time", trimmed names), which moves the embedding judge's verdict for a few students. The old noise file's 59% didn't reproduce even at the commit that wrote it, most likely because the eval reads `class_template` from the local database rather than from the commit, and that graph had been rebuilt.
  - **From now on** every result file records the git commit, the seeds and a SHA-256 fingerprint of the graph the eval read (`eval/provenance.py`), and `make eval-check` re-runs everything and fails if any committed number differs (latency excluded: it is wall time). A, B and B+ replay from the model reply cache, which is committed (`.cache/llm`: model replies only, no prompts, scanned for keys and personal data), so the whole check runs from a fresh clone after `make seed`.

**Results** (generated from [`eval/results/eval.json`](../eval/results/eval.json) and [`random_baseline.json`](../eval/results/random_baseline.json) by `scripts/readme_eval.py`):

<!-- eval:start -->
| Metric | A. No memory (n=90, seeds 0, 1, 2) | B. Vector RAG (n=90, seeds 0, 1, 2) | B+. LLM + graph as text (n=30, seed 0) | C. Unlearn (n=90, seeds 0, 1, 2) | Random guess (A / B / B+) |
| --- | --- | --- | --- | --- | --- |
| Top-1 misconception | 7% [2–12] | 7% [2–12] | 23% [10–40] | 48% [38–58] | 2.6% / 2.3% / 0.5% |
| Top-3 misconception | 7% [2–12] | 13% [7–21] | 47% [27–63] | 79% [70–87] | 7.5% / 6.8% / 1.5% |
| Root-cause accuracy | 32% [22–42] | 37% [27–47] | 40% [23–57] | 72% [63–81] | 23% / 23% / 2.5% |
| Questions to diagnosis | 6.0 [6.0–6.0] | 6.0 [6.0–6.0] | 6.0 [6.0–6.0] | 5.2 [4.9–5.4] | – |
| Session-2 recall | 0% [0–0] | 9% [3–16] | 7% [0–17] | 58% [48–67] | – |
| p50 latency per diagnosis | 14.9 s [11.1–17.3] (n=50) | 7.5 s [7.3–7.8] (n=120) | 113.8 s [113.0–115.6] (n=60) | 51 ms [49–51] (n=90) | – |
| p95 latency per diagnosis | 32.4 s [24.8–33.2] (n=50) | 9.2 s [8.6–10.2] (n=120) | 130.8 s [124.9–134.3] (n=60) | 80 ms [62–111] (n=90) | – |

Mean with its 95% bootstrap interval in brackets: 1000 resamples of students, from the saved per-student predictions (`eval/bootstrap.py`); the per-seed min–max is in [`eval/results/eval.md`](../eval/results/eval.md). Model for A, B and B+: `qwen3.5:27b-q4_K_M` (local, Ollama, thinking off), one model, no fallback. C: template wording; its metrics come from the graph.

Latency is p50 / p95 over every diagnosis timed with fresh LLM calls (cached ones are left out), pooled across the pre-review run, the Oct 18 post-review run and this run, all on the same model: n = 45 + 5 + 0 for A, 90 + 30 + 0 for B and 30 + 30 + 0 for B+, in that order. This run's A, B and B+ replies all came from the reply cache, so it timed none of them. C makes no LLM calls; its latency is this run's 90 diagnoses. `n` in a latency cell is the number of diagnoses timed.

**B+ ran on seed 0 only**, so its column above is not comparable with the other columns' three-seed means. On seed 0, the same 30 students for every condition:

| Seed 0 | A. No memory (n=30) | B. Vector RAG (n=30) | B+. LLM + graph as text (n=30) | C. Unlearn (n=30) |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 10% [0–23] | 13% [3–27] | 23% [10–40] | 50% [33–67] |
| Top-3 misconception | 10% [0–23] | 27% [13–43] | 47% [27–63] | 73% [57–90] |
| Root-cause accuracy | 33% [17–50] | 30% [13–47] | 40% [23–57] | 63% [47–80] |
| Questions to diagnosis | 6.0 [6.0–6.0] | 6.0 [6.0–6.0] | 6.0 [6.0–6.0] | 5.2 [4.8–5.6] |
| Session-2 recall | 0% [0–0] | 7% [0–17] | 7% [0–17] | 53% [37–70] |
| p50 latency per diagnosis | 18.0 s [12.4–24.8] (n=25) | 8.5 s [8.1–8.6] (n=36) | 113.8 s [113.0–115.6] (n=60) | 52 ms [50–58] (n=30) |

Candidate lists, averaged over the same students: 6.6 root-cause candidates (the target's prerequisites), 9.4 misconception candidates for A and 10 for B. A planted misconception is on A's list for 23% of students and on B's for 20%, which caps A's and B's misconception scores whatever the model does. **B+ is not capped:** it is scored on every ID it was shown, B's lists plus its graph text (410 misconceptions and 40 constructs), and every planted misconception (100%) is in it. The random-guess column picks uniformly from those same sets.

<sup>Footnote: cross-check with `gemini-3.6-flash` on seed 0 (A: n=3, B: n=2), first scoring method, **on the pre-review data** (before REVIEW.md's 2 edge deletions and 9 option removals). **Indicative only, n too small to conclude.** The Gemini free tier allows 20 requests per model per day.</sup>

| Cross-check metric | A. No memory (n=3) | B. Vector RAG (n=2) |
| --- | --- | --- |
| Top-1 misconception | 0% | 0% |
| Top-3 misconception | 0% | 0% |
| Root-cause accuracy | 0% | 50% |
<!-- eval:end -->

**What the table says.**
- **C wins on every metric.** Against A and B, over the same 90 students (seeds 0–2):
  - Root cause: 72% against 32% (A) and 37% (B), and 23% for a random pick from their own lists.
  - Misconceptions: 48% top-1 and 79% top-3, against at most 7% and 13% (B).
  - It asks fewer questions (5.2 against 6) and answers in about 51 ms (n=90) instead of 7.5 s for B (n=120) and 15 s for A (n=50), at p50.
- **B+ tests knowledge against traversal.** It ran on seed 0 only, so it is compared on seed 0's 30 students (the seed-0 table above), never with the three-seed means:
  - **Against B:** B+ beats B on root cause (40% against 30%), top-1 misconception (23% against 13%) and top-3 (47% against 27%). So the graph's knowledge does help an LLM.
  - **Against C:** it's still far behind: 40% against 63% on root cause, 23% against 50% on top-1 and 47% against 73% on top-3. Pasting the graph into the prompt doesn't reproduce what traversing it does. On seed 0, a B+ diagnosis takes 114 s at p50 (n=60), against 8.5 s for B (n=36) and 52 ms for C (n=30).
- **B+ trails C on every seed-0 metric.** With 30 students, though, the intervals overlap on top-1, top-3 and root cause; only session-2 recall is clear-cut (53% [37–70] against 7% [0–17]).
- **Uncertainty.** The bracketed 95% intervals settle the three-seed gap: C's root cause (72% [63–81]) doesn't overlap A's or B's (37% [27–47] at best). On seed 0's 30 students, C and B+ overlap on root cause (63% [47–80] against 40% [23–57]). That gap is suggestive, not conclusive.
- **Session-2 recall.** Over seeds 0–2, C scores 58% against 9% for B and 0% for A. On seed 0, C scores 53% against 7% for both B and B+, whose openings are identical.
  - The eval's figure comes from the embedding judge applied to the real opening text.
  - The 68% in the recall table under "Design decisions worth knowing" ([DESIGN.md](DESIGN.md)) counts the named IDs exactly. The two measure slightly different things.

## Is the simulator rigged in our favour?

**Yes, partly, and here is how much it matters.**
- **The bias.** The simulator picks wrong answers through the same option-to-misconception map Unlearn reads. A real student's wrong answers are messier than the map. The eval's built-in noise (a 10% guess rate, 15% of planted misconceptions not picked) blunts that bias without removing it.
- **The stress test** (`eval/noise.py`, [`eval/results/noise.json`](../eval/results/noise.json)). `noise=p` in `eval/simulator.py` adds answers the map can't explain:
  - with probability p, a uniformly random wrong option that isn't one of the student's planted misconceptions;
  - with probability p/2, a correct answer slips to a random wrong option.
- **What was re-run.** Only C, with template wording and no LLM calls. A, B and B+ keep their clean-simulator scores, which flatters them: noise would hurt them too.

| C under noise p (n=90, seeds 0–2) | Top-1 misconception | Top-3 misconception | Root cause | Session-2 recall |
| --- | --- | --- | --- | --- |
| p = 0 | 48% [38–58] | 79% [70–87] | 72% [63–81] | 58% [48–67] |
| p = 0.2 | 31% [22–40] | 58% [47–68] | 52% [42–63] | 37% [27–47] |
| p = 0.4 | 18% [10–26] | 28% [19–37] | 33% [23–44] | 17% [10–26] |
| A, clean simulator (n=90) | 7% | 7% | 32% | 0% |
| B, clean simulator (n=90) | 7% | 13% | 37% | 9% |
| B+, clean simulator (seed 0, n=30) | 23% | 47% | 40% | 7% |

| C on seed 0 only (n=30), to compare with B+ | Top-1 misconception | Top-3 misconception | Root cause | Session-2 recall |
| --- | --- | --- | --- | --- |
| p = 0 | 50% | 73% | 63% | 53% |
| p = 0.2 | 37% | 67% | 67% | 50% |
| p = 0.4 | 27% | 37% | 47% | 27% |

Brackets are 95% bootstrap intervals over students.

**What it shows.**
- **C degrades steadily with noise**, as it should: it reads exactly the evidence the noise corrupts.
- **At p = 0.2**, C still beats the clean A, B and B+ on every metric.
- **At p = 0.4**, C no longer wins everywhere:
  - Root cause (33% [23–44]) falls below clean B's 37% and only just clears A's 32%. The intervals overlap.
  - On seed 0, its top-3 (37%) falls below B+'s 47%.
  - It still beats every baseline on top-1 and session-2 recall.
- **p = 0 reproduces the main table exactly**, recall included (58%), and C's seed-0 row matches the seed-0 table. Before the Oct 19 re-run the two disagreed on recall (59% against 57%); see the note under Method.
- **A stronger model may narrow the gap** on naming misconceptions. The baselines here run on a 27B local model.

## Teacher chat tool routing (`eval/tool_routing.py`, [`eval/results/tool_routing.json`](../eval/results/tool_routing.json))

Does the chat's model pick the right graph tools for a teacher's question?
- **Method.** [`eval/tool_routing_questions.json`](../eval/tool_routing_questions.json) has 30 dev and 10 held-out natural-language questions, each with the exact set of tools that should answer it. They cover all seven chat tools, plus some two-tool questions. Each went through the real chat with `qwen3.5:27b-q4_K_M` (local, Ollama) on a copy of `class_demo`. Only the tools the model chose count.

| Set | Exact tool match | Expected tools all called |
| --- | --- | --- |
| Dev | 30 of 30 (100%) | 30 of 30 (100%) |
| Held-out | 10 of 10 (100%) | 10 of 10 (100%) |

**Read it with care:**
- **The test is easy.** We wrote the questions, they are fairly direct, and the seven tools have clearly distinct descriptions.
- **It was one run.**
- **It scores tool names, not arguments:** a right tool with the wrong student or construct would still count.
- **Nothing was tuned on the dev set**, so both sets are plain test sets.
- **Two replies fell back to the template.** In 2 of the 40 questions the model's final reply failed the receipt check twice and the template answered. Its tool choice still counts, because the model made it before the fallback.

## Concurrency (`eval/concurrency.py`, [`eval/results/concurrency.json`](../eval/results/concurrency.json))

**Both classes at once.** 30 simulated students in each of two class graphs ran at the same time through the async client. Per graph, p50 was 2.1 ms and p95 18 ms across 360 answers' worth of queries.

**Isolation.** These are small probe writes into class A, timed from a separate process with its own connection:

| Load while probing class A | p50 ms | p95 ms |
| --- | --- | --- |
| None (baseline) | 0.33 | 0.38 |
| Heavy writes on **class B** | 0.57 | 28.3 |
| Heavy writes on **class A** | 294 | 569 |
| 30 students' sessions on class B | 70 | 79 |
| 30 students' sessions on class A | 70 | 77 |

- **Write locks are per graph.** A's writes don't queue behind B's writes, only behind A's own.
- **Threads and CPU are shared.** A load that fills the server's query thread pool (`THREAD_COUNT` 15 here) slows every class equally.

**Ten classes at once** (`python eval/concurrency.py --scale-classes 10`). Ten class graphs ran with 30 simulated students each, 300 sessions at the same time, for 2.44 s:
- **Throughput:** 29,062 queries, 11,892 queries/s in total, with 0 errors.
- **Per class:** p50 24.4–24.6 ms and p95 34.9–42.6 ms; every class within a few ms of the others.
- **Probe writes** from a separate process: 0.33 ms p50 with no load, 4.44 / 8.82 ms (p50 / p95) into an idle eleventh class during the load, and 3.19 / 11.69 ms into busy class 1.
- **What limits it:** the per-session timings include queueing in the single Python test client, which runs all 300 sessions on one event loop, and the server's 15 query threads, which every class shares.
- **Where it ran:** one laptop, FalkorDB in Docker Desktop with 15 CPUs and `THREAD_COUNT` 15. It is not a multi-machine or production load test.

Tool latency for all 16 tools, 50 calls each, is in [`eval/results/latency.json`](../eval/results/latency.json). Every class-graph tool is under 5 ms at p95.
