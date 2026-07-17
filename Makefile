.PHONY: install format lint test check clean run download

download:
	python scripts/download_raw_data.py

install:
	pip install -e ".[dev]"
	pre-commit install

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/ tests/

test:
	pytest

check: lint test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .mypy_cache/

run:
	python -m ingestion_patrimoine_mtl
