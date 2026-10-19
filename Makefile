PY ?= .venv/bin/python
export PYTHONPATH := api:.

.PHONY: up dev prod down seed test topics latency demo serve real-eval eval-check

# FalkorDB only, on 127.0.0.1:6379, for running the scripts, tests and API on the host.
up:
	docker compose --profile dev up -d --wait falkordb

# FalkorDB + API (with the UI) in containers, both on loopback: http://localhost:8000
dev:
	docker compose --profile dev up -d --build --wait

# Production: only the API port (8000) is published.
prod:
	docker compose --profile prod up -d --build --wait

down:
	docker compose --profile dev --profile prod down

# The API on the host (needs `make up`): http://localhost:8000
serve:
	$(PY) -m uvicorn main:app --app-dir api --host 127.0.0.1 --port 8000

seed:
	$(PY) scripts/01_download.py
	$(PY) scripts/02_load_curriculum.py
	$(PY) scripts/03_derive.py
	$(PY) scripts/04_build_template.py
	$(PY) scripts/05_new_class.py --id demo --students 30

test:
	$(PY) -m pytest -q

topics:
	$(PY) scripts/topics.py

latency:
	$(PY) eval/latency.py --class demo --warm-sessions
	$(PY) scripts/05_new_class.py --id demo --students 30

demo:
	$(PY) scripts/demo_session.py --class demo --student $(or $(STUDENT),s01)
	$(PY) scripts/demo_session.py --class demo --student $(or $(STUDENT),s01) --session 2

# Real-data eval on Eedi NeurIPS 2020 (eval/real; data in data/external/, see eval/real/DATA.md).
# The pre-registered test run: aggregates to eval/results/real/, tables into eval/real/RESULTS.md.
real-eval:
	$(PY) -m eval.real.data
	$(PY) -m eval.real.run
	$(PY) -m eval.real.report

# Re-run the simulated eval (C, A/B/B+ from the LLM reply cache, noise, random baseline, design checks) and fail if
# any committed number in eval/results differs. Latency is not compared. See eval/check.py.
eval-check:
	$(PY) -m eval.check
