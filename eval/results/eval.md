# Eval results

30 simulated students × seeds [0, 1, 2] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 90, 'B': 90, 'B+': 30, 'C': 90}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 7% (0%–10%) | 7% (3%–13%) | 23% (23%–23%) | 48% (43%–50%) |
| Top-3 misconception | 7% (0%–10%) | 13% (7%–27%) | 47% (47%–47%) | 79% (73%–90%) |
| Root-cause accuracy | 32% (27%–37%) | 37% (30%–50%) | 40% (40%–40%) | 72% (63%–83%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | 6 (6–6) | 5.2 (5.1–5.2) |
| Session-2 recall | 0% (0%–0%) | 9% (7%–10%) | 7% (7%–7%) | 57% (50%–70%) |
| p50 latency (ms) | 17127.9 (9826.2–24429.6) | 7628.5 (7323.5–7909.3) | 113417.2 (113417.2–113417.2) | 49.5 (48.7–50.3) |
| p95 latency (ms) | 23792.0 (15845.0–31739.0) | 8362.9 (8027.7–8631.0) | 122024.9 (122024.9–122024.9) | 61.3 (57.2–65.7) |

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
