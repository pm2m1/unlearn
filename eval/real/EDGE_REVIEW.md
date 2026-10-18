# SubTopic edge review: real-data eval

The NeurIPS 2020 data tags questions only down to Eedi SubTopic, so the real-data eval runs on our 40 constructs' 7 SubTopics, with the 57 curated `REQUIRES` edges collapsed onto them (`build_subtopic_edges.py`). The collapse gives 13 SubTopic edges, and 27 construct edges are lost because both ends sit in one SubTopic. The 13 were drafted by Claude Code. **Parth reviewed them on Oct 18, 2026.** His decisions and reasons are in section 0. They are **applied** in `build_subtopic_edges.py` (`DROPPED`) and `subtopic_edges.csv`.

## 0. Decisions (Parth, Oct 18, 2026, applied)

**Rule:** keep an edge only if the target SubTopic is a genuine prerequisite; drop edges that exist only because of where Eedi files a construct.

**Summary:**
- **Edges:** 9 KEEP, 4 DROP. The kept graph must be acyclic (`tests/test_real_eval.py`).
- **Primary graph:** the 9 kept edges.
- **Sensitivity graph:** the original 13 minus edge 4 (12 edges, which also removes the 226 ↔ 227 cycle). M2, M3 and Task B also run on it, and both are reported.

| # | Edge (needs → prerequisite SubTopic) | Construct edges behind it | Decision | Reason |
| --- | --- | --- | --- | --- |
| 1 | 219 Factors & HCF → 204 Mental ×÷ | 331 → 3378, 331 → 164 | KEEP | |
| 2 | 220 Multiples & LCM → 204 Mental ×÷ | 342 → 3378 | KEEP | |
| 3 | 226 Equivalent → 204 Mental ×÷ | 409 → 3378 | KEEP | |
| 4 | 226 Equivalent → 227 Simplifying | 408 → 3342, 409 → 3342 | **DROP** | Comes only from 3342 "Read fractions", which Eedi files under 227; it also creates the 226 ↔ 227 cycle. |
| 5 | 227 Simplifying → 219 Factors & HCF | 410 → 338 (medium), 411 → 338 | KEEP | |
| 6 | 227 Simplifying → 226 Equivalent | 410 → 409, 411 → 409 | KEEP | |
| 7 | 228 Ordering → 204 Mental ×÷ | 3839 → 3193 | **DROP** | One construct edge collapsed onto the broadest SubTopic; Ordering already reaches 204 via 226 and 220. |
| 8 | 228 Ordering → 220 Multiples & LCM | 415 → 345 | KEEP | |
| 9 | 228 Ordering → 226 Equivalent | 414 → 409, 415 → 409, 3587 → 408 (low) | KEEP | |
| 10 | 228 Ordering → 227 Simplifying | 413 → 3342, 3320 → 3342, 420 → 3342 | **DROP** | Comes only from 3342 "Read fractions", not Simplifying. |
| 11 | 230 Add/Subtract → 220 Multiples & LCM | 425, 433 → 342; 426, 434, 427, 435 → 345 | KEEP | |
| 12 | 230 Add/Subtract → 226 Equivalent | 425, 433, 427, 435 → 409 | KEEP | |
| 13 | 230 Add/Subtract → 227 Simplifying | 424 → 3342, 432 → 3342 | **DROP** | Comes only from 3342 "Read fractions", not Simplifying. |

Construct edges are high confidence unless marked. Construct names are in `data/raw/construct-map.csv`; the construct edges' own review is in [REVIEW.md](../../REVIEW.md).

## Outside the graph

These Fractions SubTopics (Topic 39) contain none of our 40 constructs, so their questions are not in the eval: 225 Fractions of an Amount, 229 Converting Mixed Number and Improper Fractions, 231 Multiplying Fractions, 232 Dividing Fractions, 1162 Fractions-Others, 1982 Mixed operation Fractions.

## The primary graph (9 edges)

| SubTopic | Prerequisites (hops) | Depends on it |
| --- | --- | --- |
| 204 Mental Multiplication and Division | none | 219, 220, 226, 227, 228, 230 |
| 219 Factors and HCF | 204 (1) | 227 |
| 220 Multiples and LCM | 204 (1) | 228, 230 |
| 226 Equivalent Fractions | 204 (1) | 227, 228, 230 |
| 227 Simplifying Fractions | 219 (1), 226 (1), 204 (2) | none |
| 228 Ordering Fractions | 220 (1), 226 (1), 204 (2) | none |
| 230 Adding and Subtracting Fractions | 220 (1), 226 (1), 204 (2) | none |
