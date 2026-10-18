# Real-data results: Unlearn on Eedi NeurIPS 2020

> **Primary hypothesis (single, pre-registered).** Task A, **M2 vs M2-nograph**, AUC, 9-edge graph, all test students: do the prerequisite edges improve next-answer prediction?
> **Key secondary:** the same comparison on each student's first 2 quizzes (cold start).
> **Everything else is secondary or exploratory:** the M0, M0b, M1 and M3 comparisons, the 12-edge sensitivity graph, and all of Task B.

M2 is the **graph-structure prior, correctness-only**: a reduced Unlearn on the SubTopic graph that uses only right/wrong, **not** Unlearn's misconception reasoning. Design, metrics and deviations: [PREREGISTRATION.md](PREREGISTRATION.md). Data and licence: [DATA.md](DATA.md).

<!-- GENERATED: tables (python -m eval.real.report) -->
Run 2026-10-18 22:56:00 on test students (pre-registered), commit `9e28178`.

- **Primary:** M2 − M2-nograph AUC on all = +0.0055 [95% CI +0.0046, +0.0066]: **better**.
- **Key secondary (cold start):** M2 − M2-nograph AUC on first 2 quizzes = +0.0006 [95% CI +0.0004, +0.0009]: **negligible**.

### Task A: next-answer prediction

**All** (326,184 answers, 10,049 students)

| Model | AUC | Log-loss | Accuracy |
| --- | --- | --- | --- |
| M0 question difficulty | 0.6890 [0.6851, 0.6925] | 0.5820 [0.5776, 0.5867] | 0.6941 [0.6896, 0.6985] |
| M0b running accuracy | 0.6373 [0.6326, 0.6418] | 0.6078 [0.6030, 0.6126] | 0.6775 [0.6728, 0.6826] |
| M1 BKT | 0.6357 [0.6311, 0.6402] | 0.6063 [0.6020, 0.6107] | 0.6785 [0.6738, 0.6832] |
| M2 graph-structure prior, correctness-only | 0.7164 [0.7129, 0.7200] | 0.5674 [0.5628, 0.5721] | 0.7046 [0.7005, 0.7087] |
| M2-nograph (ablation) | 0.7108 [0.7072, 0.7144] | 0.5704 [0.5657, 0.5751] | 0.7018 [0.6977, 0.7060] |
| M3 BKT + graph prior | 0.6440 [0.6392, 0.6486] | 0.6042 [0.6000, 0.6083] | 0.6795 [0.6750, 0.6842] |
| M2, 12-edge graph | 0.7168 [0.7133, 0.7205] | 0.5671 [0.5625, 0.5718] | 0.7049 [0.7009, 0.7090] |
| M3, 12-edge graph | 0.6444 [0.6396, 0.6490] | 0.6042 [0.6000, 0.6083] | 0.6795 [0.6749, 0.6842] |

| Comparison (AUC) | Difference [95% CI] | Verdict |
| --- | --- | --- |
| M2 - M1 | +0.0807 [+0.0766, +0.0846] | better |
| M2 - M2-nograph | +0.0055 [+0.0046, +0.0066] | better |
| M3 - M1 | +0.0083 [+0.0071, +0.0095] | better |
| M0b - M1 | +0.0016 [+0.0009, +0.0024] | negligible |
| M1 - M0 | -0.0533 [-0.0589, -0.0480] | worse |
| M2 (12 edges) - M1 | +0.0811 [+0.0772, +0.0850] | better |
| M2 (12 edges) - M2-nograph | +0.0060 [+0.0051, +0.0070] | better |
| M3 (12 edges) - M1 | +0.0087 [+0.0075, +0.0099] | better |

**First 2 quizzes** (110,133 answers, 10,049 students)

| Model | AUC | Log-loss | Accuracy |
| --- | --- | --- | --- |
| M0 question difficulty | 0.6951 [0.6903, 0.6996] | 0.5814 [0.5768, 0.5860] | 0.6920 [0.6880, 0.6961] |
| M0b running accuracy | 0.5841 [0.5792, 0.5893] | 0.6274 [0.6230, 0.6315] | 0.6643 [0.6594, 0.6696] |
| M1 BKT | 0.5835 [0.5785, 0.5889] | 0.6253 [0.6213, 0.6288] | 0.6656 [0.6606, 0.6712] |
| M2 graph-structure prior, correctness-only | 0.7021 [0.6975, 0.7066] | 0.5772 [0.5726, 0.5818] | 0.6958 [0.6917, 0.7000] |
| M2-nograph (ablation) | 0.7014 [0.6968, 0.7059] | 0.5777 [0.5732, 0.5822] | 0.6953 [0.6911, 0.6994] |
| M3 BKT + graph prior | 0.5865 [0.5816, 0.5918] | 0.6247 [0.6207, 0.6281] | 0.6657 [0.6607, 0.6712] |
| M2, 12-edge graph | 0.7022 [0.6976, 0.7067] | 0.5772 [0.5726, 0.5817] | 0.6957 [0.6915, 0.6999] |
| M3, 12-edge graph | 0.5870 [0.5821, 0.5921] | 0.6246 [0.6206, 0.6281] | 0.6655 [0.6605, 0.6709] |

| Comparison (AUC) | Difference [95% CI] | Verdict |
| --- | --- | --- |
| M2 - M1 | +0.1186 [+0.1124, +0.1243] | better |
| M2 - M2-nograph | +0.0006 [+0.0004, +0.0009] | negligible |
| M3 - M1 | +0.0030 [+0.0021, +0.0039] | negligible |
| M0b - M1 | +0.0006 [-0.0001, +0.0012] | no detectable difference |
| M1 - M0 | -0.1116 [-0.1178, -0.1048] | worse |
| M2 (12 edges) - M1 | +0.1186 [+0.1125, +0.1245] | better |
| M2 (12 edges) - M2-nograph | +0.0007 [+0.0005, +0.0010] | negligible |
| M3 (12 edges) - M1 | +0.0035 [+0.0025, +0.0045] | negligible |

**Later quizzes** (216,051 answers, 8,073 students)

| Model | AUC | Log-loss | Accuracy |
| --- | --- | --- | --- |
| M0 question difficulty | 0.6856 [0.6809, 0.6902] | 0.5823 [0.5767, 0.5884] | 0.6951 [0.6894, 0.7005] |
| M0b running accuracy | 0.6615 [0.6557, 0.6671] | 0.5978 [0.5917, 0.6041] | 0.6843 [0.6785, 0.6902] |
| M1 BKT | 0.6589 [0.6534, 0.6645] | 0.5966 [0.5910, 0.6023] | 0.6851 [0.6792, 0.6908] |
| M2 graph-structure prior, correctness-only | 0.7234 [0.7190, 0.7278] | 0.5623 [0.5565, 0.5684] | 0.7091 [0.7040, 0.7142] |
| M2-nograph (ablation) | 0.7159 [0.7116, 0.7202] | 0.5666 [0.5606, 0.5730] | 0.7051 [0.6998, 0.7102] |
| M3 BKT + graph prior | 0.6691 [0.6632, 0.6748] | 0.5937 [0.5885, 0.5993] | 0.6866 [0.6808, 0.6921] |
| M2, 12-edge graph | 0.7241 [0.7198, 0.7285] | 0.5619 [0.5560, 0.5681] | 0.7096 [0.7044, 0.7146] |
| M3, 12-edge graph | 0.6696 [0.6639, 0.6753] | 0.5938 [0.5885, 0.5992] | 0.6866 [0.6808, 0.6921] |

| Comparison (AUC) | Difference [95% CI] | Verdict |
| --- | --- | --- |
| M2 - M1 | +0.0645 [+0.0597, +0.0692] | better |
| M2 - M2-nograph | +0.0076 [+0.0063, +0.0090] | better |
| M3 - M1 | +0.0101 [+0.0087, +0.0117] | better |
| M0b - M1 | +0.0026 [+0.0015, +0.0037] | negligible |
| M1 - M0 | -0.0267 [-0.0337, -0.0202] | worse |
| M2 (12 edges) - M1 | +0.0651 [+0.0604, +0.0698] | better |
| M2 (12 edges) - M2-nograph | +0.0082 [+0.0069, +0.0096] | better |
| M3 (12 edges) - M1 | +0.0106 [+0.0091, +0.0123] | better |

**A3: does the graph help more at cold start?**

| Contrast | Difference [95% CI] |
| --- | --- |
| (M2 - M2-nograph) on first 2 quizzes minus on later quizzes | -0.0069 [-0.0083, -0.0057] |
| (M2 (12 edges) - M2-nograph) on first 2 quizzes minus on later quizzes | -0.0074 [-0.0089, -0.0062] |

M3's β chosen on train: 0.2 (9 edges), 0.2 (12 edges). M2's coefficients (logit(M0), evidence, mastered, prerequisite suspicion): [1.0138, -0.0552, 0.6577, -0.0488].

### Task B: is the diagnosed root real?

| Cell | Diagnosed / test students | Roots | Method | Evaluable | Lift [95% CI] | Difficulty-adjusted lift [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| k=5, primary | 1,410 / 10,049 | 204: 749, 219: 130, 220: 170, 226: 361 | unlearn (underpowered) | 278 | +0.0644 [+0.0224, +0.1051] | +0.0412 [+0.0003, +0.0814] |
|  |  |  | random | 575 | +0.0335 [+0.0050, +0.0621] | +0.0170 [-0.0110, +0.0453] |
|  |  |  | bkt (underpowered) | 415 | +0.0720 [+0.0389, +0.1057] | +0.0420 [+0.0102, +0.0753] |
|  |  |  | unlearn_confident | 135 | +0.0379 [-0.0332, +0.1037] | +0.0310 [-0.0411, +0.0959] |
|  |  |  | unlearn - random | 205 | +0.0361 [+0.0010, +0.0735] | +0.0298 [-0.0058, +0.0663] |
|  |  |  | unlearn - bkt | 266 | -0.0089 [-0.0219, +0.0022] | -0.0045 [-0.0175, +0.0064] |
| k=10, primary | 2,323 / 10,049 | 204: 1136, 219: 242, 220: 489, 226: 456 | unlearn (underpowered) | 409 | +0.0770 [+0.0411, +0.1139] | +0.0454 [+0.0104, +0.0816] |
|  |  |  | random | 783 | +0.0415 [+0.0168, +0.0651] | +0.0212 [-0.0026, +0.0444] |
|  |  |  | bkt | 544 | +0.0695 [+0.0384, +0.0983] | +0.0372 [+0.0067, +0.0672] |
|  |  |  | unlearn_confident | 253 | +0.0667 [+0.0154, +0.1143] | +0.0387 [-0.0124, +0.0878] |
|  |  |  | unlearn - random | 326 | -0.0043 [-0.0418, +0.0299] | -0.0090 [-0.0465, +0.0247] |
|  |  |  | unlearn - bkt | 373 | -0.0049 [-0.0160, +0.0059] | -0.0056 [-0.0169, +0.0053] |
| k=5, sensitivity | 1,641 / 10,049 | 204: 733, 219: 215, 220: 131, 226: 329, 227: 233 | unlearn (underpowered) | 453 | +0.0686 [+0.0341, +0.1027] | +0.0393 [+0.0056, +0.0716] |
|  |  |  | random | 819 | +0.0616 [+0.0361, +0.0865] | +0.0304 [+0.0065, +0.0552] |
|  |  |  | bkt | 620 | +0.0772 [+0.0489, +0.1077] | +0.0401 [+0.0137, +0.0697] |
|  |  |  | unlearn_confident | 204 | +0.0613 [+0.0074, +0.1153] | +0.0487 [-0.0062, +0.1022] |
|  |  |  | unlearn - random | 419 | -0.0021 [-0.0166, +0.0141] | -0.0053 [-0.0183, +0.0089] |
|  |  |  | unlearn - bkt | 442 | -0.0087 [-0.0164, -0.0014] | -0.0057 [-0.0134, +0.0014] |
| k=10, sensitivity | 2,699 / 10,049 | 204: 1089, 219: 501, 220: 375, 226: 398, 227: 336 | unlearn | 643 | +0.0902 [+0.0623, +0.1185] | +0.0509 [+0.0239, +0.0783] |
|  |  |  | random | 1,065 | +0.0695 [+0.0483, +0.0904] | +0.0334 [+0.0130, +0.0534] |
|  |  |  | bkt | 802 | +0.0838 [+0.0583, +0.1074] | +0.0436 [+0.0187, +0.0668] |
|  |  |  | unlearn_confident | 359 | +0.0769 [+0.0333, +0.1140] | +0.0503 [+0.0070, +0.0876] |
|  |  |  | unlearn - random | 610 | +0.0036 [-0.0089, +0.0170] | +0.0008 [-0.0117, +0.0133] |
|  |  |  | unlearn - bkt | 616 | -0.0009 [-0.0070, +0.0054] | +0.0002 [-0.0055, +0.0061] |
<!-- END GENERATED -->

## Verdict

On 10,049 held-out real students, adding the prerequisite edges to a correctness-only model raised next-answer AUC by **+0.0055 [95% CI +0.0046, +0.0066]** (M2 0.7164 vs M2-nograph 0.7108). That clears the pre-registered 0.005 bar on its point estimate, so it is a small but reliable gain. Contrary to the pre-registered expectation, the gain sits in later quizzes (+0.0076 [+0.0063, +0.0090]) and is negligible at cold start (+0.0006 [+0.0004, +0.0009] on the first 2 quizzes; cold minus later −0.0069 [−0.0083, −0.0057]). In the one adequately powered Task B cell (exploratory), Unlearn's diagnosed root predicts later errors no better than a random root (+0.0036 [−0.0089, +0.0170]) or BKT's weakest skill (−0.0009 [−0.0070, +0.0054]).

## Reading the numbers

- **M2 vs BKT is not like-for-like.** M2 beats M1 by +0.0807 [+0.0766, +0.0846] AUC, but most of that is question difficulty, which M2 has and plain BKT doesn't: M0 (difficulty alone) beats M1 by +0.0533 [+0.0480, +0.0589]. The graph's own contribution is the primary comparison, +0.0055.
- **Why the cold start may show no gain** (an explanation, not measured). The prerequisite-suspicion feature is non-zero only after the student has answered something wrong on a prerequisite SubTopic in an earlier block. Early on there is little such history, so M2 and M2-nograph can barely differ there. The pre-registered expectation ("the graph helps most at cold start") did not hold. The data does not show the graph hurting early: the cold-start difference is still positive, +0.0006.
- **Direction of the graph term.** M2's coefficient on prerequisite suspicion is −0.049 per unit of evidence (9 edges; −0.050 with 12), against −0.055 for evidence on the SubTopic itself: a weak prerequisite lowers the predicted chance of a right answer, as the graph claims.
- **M3** (BKT whose prior is lowered by weak prerequisites, β = 0.2 chosen on train) beats plain BKT by +0.0083 [+0.0071, +0.0095]: the same graph signal, inside a different model.
- **12-edge sensitivity graph.** Results are nearly identical: M2 − M2-nograph +0.0060 [+0.0051, +0.0070]. The reviewed edge drops neither help nor hurt measurably.
- **Task B cells**, judged by Unlearn's evaluable students against the pre-registered 500:

  | Cell | Unlearn evaluable | Status | Unlearn − random | Unlearn − BKT |
  | --- | --- | --- | --- | --- |
  | k=5, 9 edges | 278 | underpowered, no claim | +0.0361 [+0.0010, +0.0735] | −0.0089 [−0.0219, +0.0022] |
  | k=10, 9 edges | 409 | underpowered, no claim | −0.0043 [−0.0418, +0.0299] | −0.0049 [−0.0160, +0.0059] |
  | k=5, 12 edges | 453 | underpowered, no claim | −0.0021 [−0.0166, +0.0141] | −0.0087 [−0.0164, −0.0014] |
  | k=10, 12 edges | 643 | powered | +0.0036 [−0.0089, +0.0170] | −0.0009 [−0.0070, +0.0054] |

  The generated table flags each method against 500 separately. The cell status above uses Unlearn's count, as section 6 defines it.
- **Lifts.** Every root method shows positive raw lifts, random included: later questions on dependent SubTopics are simply harder. The difficulty-adjusted lifts are 48–64% of the raw ones (Unlearn and random, all four cells).

## Limitations

- **A reduced Unlearn.** It runs on 7 SubTopics and 9 edges instead of 40 constructs and 57 edges, using right/wrong only, with no misconceptions, no question text and no adaptive questioning. These results say nothing about Unlearn's misconception reasoning, which is what the app actually does.
- **A small effect.** The primary gain's interval (+0.0046 to +0.0066) straddles the 0.005 bar. "Better" rests on the point estimate, as pre-registered.
- **Task B** is exploratory and mostly underpowered. Only 14–27% of test students get a diagnosis at all, and about half of those land on 204, which can never be evaluated in the primary graph (749 and 1,136 students at k = 5 and 10).
- **Time resolution.** Timestamps are to the minute and most quizzes are answered within one, so "history" means earlier quizzes, and the order of updates within a minute is arbitrary (AnswerId).
- **One dataset.** Eedi users 2018–2020, one platform, maths only, fractions and their prerequisites.
- **The edges** were drafted by AI and reviewed by one person (EDGE_REVIEW.md, REVIEW.md).
- **Dev exposure.** Before the test run, Claude saw dev-split metrics (train students only). Parth saw only counts. Disclosed in PREREGISTRATION.md, Deviation 6.
- **Run once.** The test split was run once (`make real-eval`, commit `9e28178`). Nothing was re-run after it.
