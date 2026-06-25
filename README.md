# Montreal Heritage Ingestion Pipeline

> **A production-grade data ingestion pipeline that transforms raw open data into enriched, RAG-ready records — with contractual data quality, full reproducibility, and French NLP.**

This pipeline ingests the **2,742 heritage buildings** from [Données Québec](https://www.donneesquebec.ca) — the open data portal born from the collaboration between Québec municipalities and the provincial government — applies multi-stage cleaning and validation, extracts named entities with spaCy, and produces structured JSONL records consumed by [rag-engine](https://github.com/LudovicJulien/rag-engine).

![Version](https://img.shields.io/badge/version-0.1.0-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-green)
![DVC](https://img.shields.io/badge/DVC-3.50+-purple)
![License](https://img.shields.io/badge/license-MIT-blue)
![Lint](https://img.shields.io/badge/lint-ruff%20%7C%20mypy%20strict-informational)

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
Données Québec open data portal (donneesquebec.ca)
         │
         ▼  make download
rawData/edifices_patrimoine.csv  (2,742 buildings · 16 columns)
         │
         ▼  [01 · Ingest]
         │  chardet encoding detection · SHA-256 per-row hashing · idempotency
         │  metadata injection (ingested_at, source_file, pipeline_version)
         ▼
data/01_raw/buildings_raw.parquet          ← RawSchema (Pandera)
         │
         ▼  [02 · Clean]
         │  BeautifulSoup HTML stripping · ftfy encoding repair
         │  French typography normalization · whitespace collapsing
         ▼
data/02_clean/buildings_clean.parquet      ← CleanSchema (Pandera)
         │
         ▼  [03 · Normalize]
         │  Pydantic v2 record validation · date range enforcement [1600–2030]
         │  Montreal bbox coordinate check · 19-borough arrondissement validation
         │  TYPE_DE_VOIE / EST_OUEST canonical normalization · data quality report
         ▼
data/03_normalized/buildings_normalized.parquet   ← NormalizedSchema (Pandera)
         │
         ▼  [04 · Enrich]
         │  spaCy fr_core_news_lg batch NER · entity extraction (PER, ORG, LOC, DATE)
         │  BuildingEnriched assembly · JSONL serialization
         ▼
data/04_enriched/buildings_enriched.jsonl
         │
         ▼
  rag-engine  (chunking · embedding · indexing — out of scope)
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

---

## Data Quality Challenges (and how each stage handles them)

| Challenge | Stage | Solution |
|-----------|-------|----------|
| Unknown file encoding | 01 | `chardet` detects encoding before `pandas.read_csv` |
| HTML in `HISTORIQUE_SOMMAIRE` | 02 | `BeautifulSoup` with `html.parser` |
| Encoding artifacts in French text | 02 | `ftfy.fix_text()` on all string columns |
| Curly apostrophes / guillemets inconsistency | 02 | Custom French typography normalizer |
| Construction dates outside plausible range | 03 | Pydantic validator: `[1600, 2030]`, nullify on violation |
| Coordinates outside Montreal island | 03 | `is_in_montreal_bbox()` against WGS84 bbox |
| Non-canonical borough names | 03 | Validated against official 19-arrondissement list |
| Flat text without entity metadata | 04 | spaCy `fr_core_news_lg` batch NER → structured `BuildingEntities` |

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
    "locations": ["Montréal", "rue McGill"]
  },
  "record_hash": "a3f2c1...",
  "ingested_at": "2026-06-09T14:00:00Z",
  "pipeline_version": "0.1.0"
}
```

---

## Quick Start

```bash
git clone https://github.com/LudovicJulien/montreal-heritage-ingestion.git
cd montreal-heritage-ingestion
make install      # install deps + pre-commit hooks
make download     # fetch raw CSV from Données Montréal
dvc repro         # run all 4 stages (skips unchanged ones)
make lint         # ruff + mypy strict
make test         # pytest with coverage report
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
make install       # installs deps + pre-commit hooks
```

### Run the full pipeline

```bash
make download      # fetch raw CSV from Données Montréal (~1 MB)
dvc repro          # run all 4 stages, skip unchanged ones
```

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

```bash
make lint          # ruff check + ruff format + mypy strict
make test          # pytest with coverage report
```

Pre-commit runs `ruff`, `ruff-format`, and `mypy` on every commit.

### Environment variables

All settings are managed by `pydantic-settings` and can be overridden via `.env` or environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `INGESTION_RAW_DATA_DIR` | `rawData` | Source CSV directory |
| `INGESTION_DATA_DIR` | `data` | Pipeline output root |
| `INGESTION_LOG_LEVEL` | `INFO` | Logging level |
| `INGESTION_LOG_FORMAT` | `dev` | `dev` (colored) or `json` (structured) |

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

---

## Project Structure

```
montreal-heritage-ingestion/
├── src/ingestion_patrimoine_mtl/
│   ├── config.py           # Pydantic BaseSettings — paths + pipeline flags
│   ├── models.py           # BuildingRaw · BuildingEntities · BuildingEnriched
│   ├── schemas.py          # Pandera DataFrame contracts per stage
│   ├── pipeline/
│   │   ├── s01_ingest.py   # Encoding detection · hashing · idempotency
│   │   ├── s02_clean.py    # HTML · ftfy · French typography
│   │   ├── s03_normalize.py # Pydantic validation · geo · address normalization
│   │   └── s04_enrich.py   # spaCy NER · JSONL export
│   └── utils/
│       ├── hashing.py      # SHA-256 per-row · DataFrame hashing
│       ├── geo.py          # Montreal bbox · Lambert→WGS84 · borough list
│       └── logging.py      # loguru setup (dev / json)
├── scripts/
│   └── download_raw_data.py  # Fetch CSV from Données Montréal + integrity check
├── tests/
│   ├── unit/               # Isolated tests per utility and stage
│   └── integration/        # End-to-end pipeline on sample records
├── data/                   # Pipeline outputs (DVC-tracked, git-ignored)
│   ├── 01_raw/
│   ├── 02_clean/
│   ├── 03_normalized/
│   └── 04_enriched/
├── dvc.yaml                # 4-stage DVC pipeline definition
└── rawData/                # Source CSV (git-ignored, reproducible via make download)
```

---

## Related

This pipeline is the data preparation layer for **[rag-engine](https://github.com/LudovicJulien/rag-engine)** — a production-grade RAG backend with hybrid retrieval (BM25 + dense), multi-provider LLM support, and full observability.

```
montreal-heritage-ingestion  →  buildings_enriched.jsonl  →  rag-engine
```

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.
