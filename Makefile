.PHONY: install lint test run download

download:
	python scripts/download_raw_data.py

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check --fix src/ tests/
	ruff format src/ tests/
	mypy src/ tests/


test:
	pytest

run:
	python -m ingestion_patrimoine_mtl
