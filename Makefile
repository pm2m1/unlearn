PY ?= .venv/bin/python
export PYTHONPATH := api:.

.PHONY: up down seed test topics

up:
	docker compose up -d --wait falkordb

down:
	docker compose down

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
