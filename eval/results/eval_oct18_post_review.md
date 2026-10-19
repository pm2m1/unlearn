# Eval results

30 simulated students × seeds [0, 1, 2] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 90, 'B': 90, 'B+': 30, 'C': 90}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 7% (0%–10%) | 7% (3%–13%) | 23% (23%–23%) | 48% (43%–50%) |
| Top-3 misconception | 7% (0%–10%) | 13% (7%–27%) | 47% (47%–47%) | 79% (73%–90%) |
| Root-cause accuracy | 32% (27%–37%) | 37% (30%–50%) | 40% (40%–40%) | 72% (63%–83%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | 6 (6–6) | 5.2 (5.1–5.2) |
| Session-2 recall | 0% (0%–0%) | 9% (7%–10%) | 7% (7%–7%) | 57% (50%–70%) |
| p50 latency (ms) | 14876.2 (n=50) | 7495.7 (n=120) | 113796.5 (n=60) | 49.5 (n=90) |
| p95 latency (ms) | 32361.7 (n=50) | 9223.7 (n=120) | 130759.1 (n=60) | 60.9 (n=90) |

Latency: p50 / p95 over every timed diagnosis in eval_pre_review, eval (A, B, B+; C from this run only), n = diagnoses timed.

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
