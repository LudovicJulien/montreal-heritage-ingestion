.PHONY: install lint test run download

download:
	python scripts/download_raw_data.py

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src/
	ruff format --check src/
	mypy src/

test:
	pytest

run:
	python -m ingestion_patrimoine_mtl
