# Eval results

30 simulated students × seeds [0, 1, 2] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 90, 'B': 90, 'B+': 30, 'C': 90}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 6% (0%–10%) | 8% (3%–17%) | 17% (17%–17%) | 47% (40%–50%) |
| Top-3 misconception | 6% (0%–10%) | 11% (3%–23%) | 33% (33%–33%) | 78% (73%–87%) |
| Root-cause accuracy | 28% (23%–33%) | 37% (27%–47%) | 37% (37%–37%) | 73% (67%–80%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | 6 (6–6) | 5.3 (5.2–5.4) |
| Session-2 recall | 0% (0%–0%) | 10% (10%–10%) | 10% (10%–10%) | 56% (50%–63%) |
| p50 latency (ms) | 12581.9 (9395.4–17770.4) | 7602.7 (6976.0–8559.5) | 114076.3 (114076.3–114076.3) | 50.5 (50.1–50.8) |
| p95 latency (ms) | 23309.5 (18165.9–32440.9) | 8627.4 (7799.3–10250.5) | 133112.7 (133112.7–133112.7) | 72.7 (56.4–92.5) |

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
