# Eval results

30 simulated students × seeds [0, 1, 2] × 2 sessions. Mean (min–max across seeds). LLM: none (template wording).

| Metric | A. No memory | B. Vector RAG | C. Unlearn |
| --- | --- | --- | --- |
| Top-1 misconception | not run | not run | 47% (40%–50%) |
| Top-3 misconception | not run | not run | 78% (73%–87%) |
| Root-cause accuracy | not run | not run | 73% (67%–80%) |
| Questions to diagnosis | not run | not run | 5.3 (5.2–5.4) |
| Session-2 recall | not run | not run | 30% (27%–33%) |
| p50 latency (ms) | not run | not run | 50.3 (50.1–50.6) |
| p95 latency (ms) | not run | not run | 63.3 (58.5–66.5) |

A. No memory not run: no LLM API key configured

B. Vector RAG not run: no LLM API key configured

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
