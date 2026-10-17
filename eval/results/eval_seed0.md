# Eval results

30 simulated students × seeds [0] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 30, 'B': 30, 'B+': 30, 'C': 30}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 7% (7%–7%) | 17% (17%–17%) | 10% (10%–10%) | 50% (50%–50%) |
| Top-3 misconception | 7% (7%–7%) | 23% (23%–23%) | 20% (20%–20%) | 73% (73%–73%) |
| Root-cause accuracy | 27% (27%–27%) | 27% (27%–27%) | 37% (37%–37%) | 67% (67%–67%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | 6 (6–6) | 5.2 (5.2–5.2) |
| Session-2 recall | 0% (0%–0%) | 10% (10%–10%) | 10% (10%–10%) | 50% (50%–50%) |
| p50 latency (ms) | 17770.4 (17770.4–17770.4) | 8559.5 (8559.5–8559.5) | 114076.3 (114076.3–114076.3) | 50.1 (50.1–50.1) |
| p95 latency (ms) | 32440.9 (32440.9–32440.9) | 10250.5 (10250.5–10250.5) | 133112.7 (133112.7–133112.7) | 92.5 (92.5–92.5) |

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
