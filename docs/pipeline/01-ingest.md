# Stage 01 — `s01_ingest.py`

This document explains, function by function, what `s01_ingest.py` does, with examples taken from the project's real data (`data/01_raw/buildings_raw.parquet`).

For architectural context (why four stages, why Parquet, why a SHA-256 hash), see [ADR-001](../adr/ADR-001-four-stage-pipeline-architecture.md) and [ADR-003](../adr/ADR-003-sha256-row-hashing-for-idempotence.md).

Next stage: [02 — Clean](02-clean.md).

---

**Input**: `rawData/edifices_patrimoine.csv` (downloaded from Données Montréal via `scripts/download_raw_data.py`)
**Output**: `data/01_raw/buildings_raw.parquet`

### `run(cfg)` — orchestration

Runs the sub-steps below in order, then logs the number of rows processed.

### `_ensure_source_exists`

Checks that the source CSV exists before anything else. If it is missing, raises an explicit error that states how to retrieve it (`make download`).

### `_detect_encoding`

Detects the file encoding from a 100,000-byte sample:
1. Attempts a strict UTF-8 decode — if it succeeds, the file is UTF-8.
2. Otherwise, falls back to `chardet`.

### `_load_csv`

Loads the CSV in chunks of 500 rows (`tqdm` progress bar), with **`dtype=str` everywhere**. No typing is done at this stage: ingestion must preserve the raw fidelity of the data (e.g. leading zeros in identifiers).

**Example** — `identifiant_batiment` stays a string, leading zero preserved:

| Column | Value |
|---|---|
| `identifiant_batiment` | `"0039-27-4599-00"` |

Had this column been cast to a number, the `0039` prefix would have lost its meaning.

### `_strip_column_spaces` + `_normalize_column_names`

Cleans up the CSV headers: trims whitespace, then lowercases.

**Example** — raw CSV header:
```
IDENTIFIANT_BATIMENT,NOM_HISTORIQUE ,TYPOLOGIE_SPECIFIQUE,...,HISTORIQUE_SOMMAIRE ,...
```
becomes, after these two functions:
```
identifiant_batiment, nom_historique, typologie_specifique, ..., historique_sommaire, ...
```
(`NOM_HISTORIQUE ` and `HISTORIQUE_SOMMAIRE ` had a trailing space in the source CSV.)

### `_add_row_hashes`

Computes a deterministic per-row SHA-256 hash over the **raw** columns only (before the pipeline metadata is added), and inserts it into `record_hash`.

**Example**:

| `identifiant_batiment` | `record_hash` |
|---|---|
| `0039-27-4599-00` | `97f3296907de73d04e381768ed84dd2dbc508eae6a41f694a977b0c2f42a28c8` |

### `_idempotence_filter`

If `buildings_raw.parquet` already exists from a previous run, keeps only the rows whose `record_hash` is **not** already known. On the first run, every row passes. This prevents duplicate records when re-running against the same CSV (or a partially updated one).

### `_add_metadata`

Adds three pipeline columns, always non-null:

| Column | Example |
|---|---|
| `ingested_at` | `2026-06-25 20:30:44.381678` (UTC) |
| `source_file` | `edifices_patrimoine.csv` |
| `pipeline_version` | `0.1.0` (at the time of this run) |

### `_validate_schema`

Validates the DataFrame against `RawSchema` (pandera). Columns coming from the CSV are nullable (ingestion rejects no row for missing data); the pipeline columns (`record_hash`, `ingested_at`, `source_file`, `pipeline_version`) are required.

### `_write_parquet`

Writes the result as compressed Parquet (snappy) to `data/01_raw/buildings_raw.parquet`.
