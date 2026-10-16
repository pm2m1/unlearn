# Unlearn

> **Remove-FalkorDB test:** without the graph there is no misconception-to-concept grounding, no prerequisite root-cause traversal, no per-class memory, no agent handoffs and no cohort grouping. It collapses into generic chat.

Work in progress for Graph Hacks (WeMakeDevs × FalkorDB). See `SPEC.md` for the build spec.

## Setup (so far)

```
cp .env.example .env        # set FALKOR_PASSWORD
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
make up && make seed && make test
```

## Data

"[Eedi Misconceptions Graph v1.0](https://huggingface.co/datasets/Eedi/Eedi-Misconceptions-Graph)" by Eedi, licensed under CC BY 4.0. Adapted: filtered to Number/Fractions for the class graphs, with curated prerequisite edges and generated questions added.
Source: `Eedi/Eedi-Misconceptions-Graph` on Hugging Face, pinned to commit `2ae0839d`.

AI assistant use is disclosed in [AI_USAGE.md](AI_USAGE.md).
