.PHONY: install format lint test check clean run download rpcq-download

download:
	python scripts/download_raw_data.py

# Both Données Québec exports (CC-BY 4.0) — classés and cités. See ADR-005.
rpcq-download:
	python scripts/download_rpcq_data.py

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
