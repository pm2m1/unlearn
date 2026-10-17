# Eval results

30 simulated students × seeds [1, 2] × 2 sessions. Mean (min–max across seeds). A/B model: ollama / qwen3.5:27b-q4_K_M; C: template wording. n per condition: {'A': 60, 'B': 60, 'C': 60}.

| Metric | A. No memory | B. Vector RAG | B+. LLM + graph as text | C. Unlearn |
| --- | --- | --- | --- | --- |
| Top-1 misconception | 5% (0%–10%) | 3% (3%–3%) | not run | 45% (40%–50%) |
| Top-3 misconception | 5% (0%–10%) | 5% (3%–7%) | not run | 80% (73%–87%) |
| Root-cause accuracy | 28% (23%–33%) | 42% (37%–47%) | not run | 77% (73%–80%) |
| Questions to diagnosis | 6 (6–6) | 6 (6–6) | not run | 5.3 (5.3–5.4) |
| Session-2 recall | 0% (0%–0%) | 10% (10%–10%) | not run | 58% (53%–63%) |
| p50 latency (ms) | 9987.6 (9395.4–10579.8) | 7124.2 (6976.0–7272.5) | not run | 50.8 (50.7–50.8) |
| p95 latency (ms) | 18743.8 (18165.9–19321.8) | 7815.9 (7799.3–7832.5) | not run | 62.8 (56.4–69.1) |

B+. LLM + graph as text not run: not requested

The simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.
