# Eval results

30 simulated students × seeds [0, 1, 2] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 90, 'B': 90, 'B+': 30, 'C': 90}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 9% (0%–17%) | 7% (3%–13%) | 23% (23%–23%) | 48% (43%–50%) |
| Top-3 misconception | 10% (3%–17%) | 13% (7%–27%) | 40% (40%–40%) | 79% (73%–90%) |
| Root-cause accuracy | 30% (27%–37%) | 38% (33%–47%) | 40% (40%–40%) | 72% (63%–83%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | 6 (6–6) | 5.2 (5.1–5.2) |
| Session-2 recall | 0% (0%–0%) | 9% (7%–10%) | 7% (7%–7%) | 60% (50%–77%) |
| p50 latency (ms) | 13303.2 (n=62) | 7743.9 (n=151) | 114413.1 (n=68) | 52.4 (n=90) |
| p95 latency (ms) | 32178.6 (n=62) | 9233.9 (n=151) | 137043.8 (n=68) | 98.7 (n=90) |

Latency: p50 / p95 over every timed diagnosis in eval_pre_review, eval_oct18_post_review, eval (A, B, B+; C from this run only), n = diagnoses timed.

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
