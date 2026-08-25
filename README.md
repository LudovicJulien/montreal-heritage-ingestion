# Montreal Heritage Ingestion Pipeline

> **A production-grade data ingestion pipeline that transforms raw open data into enriched, RAG-ready records — with contractual data quality, full reproducibility, and French NLP.**

This pipeline ingests the **1,336 heritage buildings** published by [Données Montréal](https://donnees.montreal.ca), the Ville de Montréal open data portal, applies multi-stage cleaning and validation, and extracts named entities with spaCy to produce structured JSONL records ready for downstream retrieval systems.

> The source file counts 1,336 records over 2,743 physical lines: 272 buildings carry a multi-paragraph `HISTORIQUE_SOMMAIRE` with embedded newlines. Line counts are not record counts here — see [03-normalize.md](docs/pipeline/03-normalize.md).

![CI](https://github.com/LudovicJulien/montreal-heritage-ingestion/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.4.0-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-green)
![DVC](https://img.shields.io/badge/DVC-3.50+-purple)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)
![Lint](https://img.shields.io/badge/lint-ruff%20%7C%20mypy%20strict-informational)

---

## Project Status

The pipeline is being built stage by stage. Stages 01, 01b and 02 to 03 are implemented, tested,
and locked in DVC; stage 04 exists as a typed skeleton.

| Stage | Status | Notes |
|---|---|---|
| 01 · Ingest | ✅ **Implemented** | Encoding detection, SHA-256 hashing, idempotence, `RawSchema` |
| 01b · Ingest RPCQ | ✅ **Implemented** | Second source: two Données Québec exports reconciled into 179 Montreal records, `RpcqRawSchema` — see [01b-rpcq.md](docs/pipeline/01b-rpcq.md) and [ADR-005](docs/adr/ADR-005-rpcq-as-secondary-source.md) |
| 02 · Clean | ✅ **Implemented** | HTML stripping, ftfy, French typography, `CleanSchema` |
| 03 · Normalize | ✅ **Implemented** | Borough canonicalization, sentinel-year nullification, WGS84 validation, `NormalizedSchema` — see [03-normalize.md](docs/pipeline/03-normalize.md) and [ADR-004](docs/adr/ADR-004-data-quality-policy.md) |
| 04 · Enrich | ⏳ **Planned** | spaCy is not yet a declared dependency |

`dvc repro` runs stages 01, 01b and 02–03, and stops at `s04_enrich`. The unit tests for stage 04 and the
end-to-end integration tests are `@pytest.mark.skip` placeholders naming the cases to cover.

---

## Why This Exists

Open heritage data is messy in ways that break naive pipelines:

- CSV fields contain **raw HTML tags** (`<i>dry goods</i>`) embedded in historical summaries
- **Encoding corruption** from legacy municipal exports requires detection before parsing
- **Coordinate systems** need explicit validation against the Montreal bounding box
- **Address normalization** varies across boroughs (`Rue` vs `rue`, `E` vs `Est`)
- Historical text without NER produces flat chunks that defeat semantic retrieval

This pipeline solves each of these problems with a dedicated stage, contractual DataFrame schemas between every transition, and full DVC reproducibility.

---

## Pipeline Architecture

```
Données Montréal open data portal (donnees.montreal.ca)
         |
         v  make download
rawData/edifices_patrimoine.csv  (1,336 buildings · 16 columns)
         |
         v  [01 · Ingest]
         |  chardet encoding detection · SHA-256 per-row hashing · idempotency
         |  metadata injection (ingested_at, source_file, pipeline_version)
         v
data/01_raw/buildings_raw.parquet          <- RawSchema (Pandera)
         |
         |    Données Québec open data (donneesquebec.ca) — CC-BY 4.0
         |             |
         |             v  make rpcq-download
         |    rawData/rpcq/*.csv  (621 classés + 730 cités)
         |             |
         |             v  [01b · Ingest RPCQ]
         |             |  two column layouts reconciled · WKT -> lat/lon · regime tagging
         |             |  Montreal region filter (1,351 -> 179) · SHA-256 hashing
         |             v
         |    data/01b_rpcq/rpcq_raw.parquet   <- RpcqRawSchema (Pandera)
         |             |
         |             '--- joined at stage 04 (fuzzy: no join key exists)
         |
         v  [02 · Clean]
         |  BeautifulSoup HTML stripping · ftfy encoding repair
         |  French typography normalization · whitespace collapsing
         v
data/02_clean/buildings_clean.parquet      <- CleanSchema (Pandera)
         |
         v  [03 · Normalize]
         |  borough canonicalization (suffix · em dash · apostrophe) + agglomeration allowlist
         |  sentinel-year nullification [1600-2030] · Montreal WGS84 bbox check
         |  TYPE_DE_VOIE / EST_OUEST normalization · municipalite_type tagging · quality report
         v
data/03_normalized/buildings_normalized.parquet   <- NormalizedSchema (Pandera)
         |
         v  [04 · Enrich]
         |  spaCy fr_core_news_lg batch NER · entity extraction (PER, ORG, LOC, DATE)
         |  BuildingEnriched assembly · JSONL serialization
         v
data/04_enriched/buildings_enriched.jsonl
```

**Key design decisions:**

- **Parquet between stages** — columnar format preserves types across boundaries; no schema drift between runs
- **Pandera contracts** — each stage transition is gated by an explicit DataFrame schema; bad data fails loudly, not silently
- **SHA-256 idempotency** — records already processed on a previous run are skipped without re-computation
- **DVC pipeline** — `dvc repro` re-runs only the stages downstream of what changed; the full 4-stage run is a single command

### Architecture Decision Records

The key design choices are documented as ADRs in [`docs/adr/`](docs/adr/):

| ADR | Decision |
|-----|----------|
| [ADR-001](docs/adr/ADR-001-four-stage-pipeline-architecture.md) | Why four stages instead of one monolithic script |
| [ADR-002](docs/adr/ADR-002-dvc-for-pipeline-orchestration.md) | Why DVC over Airflow, Bash scripts, or Git LFS |
| [ADR-003](docs/adr/ADR-003-sha256-row-hashing-for-idempotence.md) | Why SHA-256 per-row hashing for idempotent re-runs |
| [ADR-004](docs/adr/ADR-004-data-quality-policy.md) | When to reject a row, nullify a field, or normalize a value |
| [ADR-005](docs/adr/ADR-005-rpcq-as-secondary-source.md) | Why the RPCQ open data exports come before scraping |

### Stage-by-Stage Documentation

A function-by-function walkthrough of each stage, with real examples from the dataset, lives in [`docs/pipeline/`](docs/pipeline/):

| Stage | Doc |
|-------|-----|
| 01 · Ingest | [docs/pipeline/01-ingest.md](docs/pipeline/01-ingest.md) |
| 01b · Ingest RPCQ | [docs/pipeline/01b-rpcq.md](docs/pipeline/01b-rpcq.md) — walkthrough + open data profile |
| 02 · Clean | [docs/pipeline/02-clean.md](docs/pipeline/02-clean.md) |
| 03 · Normalize | [docs/pipeline/03-normalize.md](docs/pipeline/03-normalize.md) — walkthrough + data profile |

---

## Data Quality Challenges (and how each stage handles them)

| Challenge | Stage | Solution |
|-----------|-------|----------|
| Unknown file encoding | 01 | `chardet` detects encoding before `pandas.read_csv` |
| HTML in `NOM_HISTORIQUE` / `HISTORIQUE_SOMMAIRE` | 02 | `BeautifulSoup` with `html.parser` |
| Encoding artifacts in French text | 02 | `ftfy.fix_text()` on all string columns |
| Curly apostrophes / guillemets inconsistency | 02 | Custom French typography normalizer |
| Construction dates outside plausible range | 03 | Pydantic validator: `[1600, 2030]`, nullify on violation |
| Coordinates outside Montreal island | 03 | `is_in_montreal_bbox()` against WGS84 bbox |
| Borough labels matching no official name | 03 | `canonicalize_municipality()` — suffix, em dash and apostrophe — then the 19 boroughs + 15 villes liées allowlist |
| Flat text without entity metadata | 04 | spaCy `fr_core_news_lg` batch NER -> structured `BuildingEntities` |

---

## Output Format

Each record in `buildings_enriched.jsonl` is a self-contained building object:

```json
{
  "id": "0039-27-4599-00",
  "nom_historique": "Maisons-magasins Jacob-De Witt I",
  "typologie": "Immeuble commercial",
  "adresse": "365, rue McGill",
  "arrondissement": "Ville-Marie",
  "latitude": 45.5019,
  "longitude": -73.5548,
  "debut_travaux": 1846,
  "fin_travaux": 1847,
  "text": "Construit en 1846 pour le marchand Jacob De Witt...",
  "entities": {
    "persons": ["Jacob De Witt"],
    "orgs": [],
    "dates": ["1846"],
    "locations": ["Montreal", "rue McGill"]
  },
  "record_hash": "a3f2c1...",
  "ingested_at": "2026-06-09T14:00:00Z",
  "pipeline_version": "0.4.0"
}
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- `make`

### Installation

```bash
git clone https://github.com/LudovicJulien/montreal-heritage-ingestion.git
cd montreal-heritage-ingestion
make install       # install deps + pre-commit hooks
```

### Configure your DVC remote

DVC tracks pipeline artifacts (Parquet, JSONL). Each contributor sets their own local remote path:

```bash
dvc remote add -d local /your/path/to/dvc-store --local
```

The URL is written to `.dvc/config.local` which is gitignored — your path never reaches the repository.

### Run the full pipeline

```bash
make download      # fetch raw CSV from Données Montréal (~720 KB)
make rpcq-download # fetch both RPCQ exports from Données Québec (~4.8 MB)
dvc repro          # run the implemented stages, skip unchanged ones
```

> `dvc repro` currently completes stages 01 to 03, then stops at `s04_enrich`, which is not
> implemented yet. See [Project Status](#project-status).

### Run a single stage

```bash
python -m ingestion_patrimoine_mtl --stage 01
python -m ingestion_patrimoine_mtl --stage 02 --log-format json
```

### Reproduce from scratch

```bash
dvc repro --force  # ignore cache, re-run everything
```

---

## Development

### Make targets

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies and pre-commit hooks |
| `make format` | Auto-format and fix linting issues (ruff) |
| `make lint` | Check formatting, style, and types without modifying files |
| `make test` | Run pytest with coverage report |
| `make check` | Run `lint` then `test` in sequence (used in CI) |
| `make clean` | Remove `__pycache__`, `.coverage`, `htmlcov/`, `.mypy_cache/` |
| `make download` | Fetch source CSV from Données Montréal |
| `make rpcq-download` | Fetch both RPCQ exports from Données Québec (CC-BY 4.0) |
| `make run` | Run the full pipeline via `python -m ingestion_patrimoine_mtl` |

### Pre-commit hooks

Pre-commit runs automatically on every commit:

| Hook | Purpose |
|------|---------|
| `trailing-whitespace` | Remove trailing spaces |
| `end-of-file-fixer` | Ensure files end with a newline |
| `check-merge-conflict` | Block commits with unresolved conflict markers |
| `check-yaml` | Validate YAML syntax |
| `ruff` | Lint and auto-fix Python |
| `ruff-format` | Format Python |
| `mypy` | Type-check with strict mode |

### Environment variables

All settings are managed by `pydantic-settings`. Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `INGESTION_RAW_DATA_DIR` | `rawData` | Source CSV directory |
| `INGESTION_SOURCE_FILE` | `edifices_patrimoine.csv` | Source CSV filename |
| `INGESTION_DATA_DIR` | `data` | Pipeline output root |
| `INGESTION_PIPELINE_VERSION` | `0.4.0` | Version stamped on every ingested row |
| `INGESTION_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `INGESTION_LOG_FORMAT` | `dev` | `dev` (colored) or `json` (structured, for CI/prod) |

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Data versioning | DVC 3.50+ | Stage-level reproducibility, output caching |
| DataFrame contracts | Pandera 0.20 | Schema validation at every stage boundary |
| Data modeling | Pydantic v2 | `BuildingRaw`, `BuildingEnriched` domain models |
| Text cleaning | BeautifulSoup + ftfy | HTML stripping + encoding repair |
| Encoding detection | chardet | Auto-detect before CSV parsing |
| NER | spaCy `fr_core_news_lg` | French named entity recognition |
| Geo validation | Custom + WGS84 bbox | Montreal island boundary + 19 boroughs |
| Serialization | Parquet (pyarrow) + JSONL | Typed intermediates, flat final output |
| Config | pydantic-settings | `.env` + env vars, typed, validated |
| Logging | loguru | Colored dev output, JSON mode for CI |
| Linting | ruff + mypy strict | Enforced on every commit via pre-commit |
| CI | GitHub Actions | Parallel lint and test jobs on every push and PR |

---

## Project Structure

```
montreal-heritage-ingestion/
├── src/ingestion_patrimoine_mtl/
│   ├── config.py            # Pydantic BaseSettings — paths + pipeline flags
│   ├── models.py            # BuildingRaw · RpcqBuilding · BuildingEntities · BuildingEnriched
│   ├── schemas.py           # Pandera DataFrame contracts per stage
│   ├── pipeline/
│   │   ├── s01_ingest.py    # Encoding detection · hashing · idempotency
│   │   ├── s01b_rpcq.py     # RPCQ open data · layout reconciliation · region filter
│   │   ├── s02_clean.py     # HTML · ftfy · French typography
│   │   ├── s03_normalize.py # Pydantic validation · geo · address normalization
│   │   └── s04_enrich.py    # spaCy NER · JSONL export
│   └── utils/
│       ├── hashing.py       # SHA-256 per-row · DataFrame hashing
│       ├── geo.py           # Montreal bbox · Lambert->WGS84 · borough list
│       └── logging.py       # loguru setup (dev / json)
├── scripts/
│   ├── download_raw_data.py # Fetch CSV from Données Montréal + integrity check
│   └── download_rpcq_data.py # Fetch both RPCQ exports from Données Québec
├── tests/
│   ├── unit/                # Isolated tests per utility and stage
│   └── integration/         # End-to-end pipeline on sample records
├── docs/adr/                # Architecture Decision Records
├── docs/pipeline/           # Stage-by-stage walkthrough (01-ingest.md, 01b-rpcq.md, 02-clean.md, 03-normalize.md)
├── data/                    # Pipeline outputs (DVC-tracked, git-ignored)
│   ├── 01_raw/
│   ├── 01b_rpcq/
│   ├── 02_clean/
│   ├── 03_normalized/
│   └── 04_enriched/
├── .env.example             # Environment variable reference
├── dvc.yaml                 # 5-stage DVC pipeline definition
└── rawData/                 # Source CSVs (git-ignored, reproducible via make download / rpcq-download)
```

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.
