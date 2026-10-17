# Eval results

3 simulated students × seeds [0] × 2 sessions. Mean (min–max across seeds). A/B model: gemini / gemini-3.6-flash; C: template wording. n per condition: {'A': 3, 'B': 2}.

| Metric | A. No memory | B. Vector RAG | C. Unlearn |
| --- | --- | --- | --- |
| Top-1 misconception | 0% (0%–0%) | 0% (0%–0%) | not run |
| Top-3 misconception | 0% (0%–0%) | 0% (0%–0%) | not run |
| Root-cause accuracy | 0% (0%–0%) | 50% (50%–50%) | not run |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | not run |
| Session-2 recall | 0% (0%–0%) | 0% (0%–0%) | not run |
| p50 latency (ms) | 9721.3 (9721.3–9721.3) | 2032.4 (2032.4–2032.4) | not run |
| p95 latency (ms) | 64753.2 (64753.2–64753.2) | 2349.0 (2349.0–2349.0) | not run |

C. Unlearn not run: not requested

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
