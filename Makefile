PYTHON ?= .venv/bin/python

.PHONY: install test lint run-api scrape index smoke

install:
	uv pip install --python $(PYTHON) -r backend/requirements-dev.txt

test:
	PYTHONPATH=. $(PYTHON) -m pytest

run-api:
	PYTHONPATH=. $(PYTHON) -m uvicorn backend.app.main:app --reload

scrape:
	PYTHONPATH=. $(PYTHON) -m scraper.run_all

index:
	PYTHONPATH=. $(PYTHON) -m ingestion.build_index

smoke:
	PYTHONPATH=. $(PYTHON) -m pytest -q
	docker compose config --quiet
	docker build -f backend/Dockerfile -t estatebot-api:local .
