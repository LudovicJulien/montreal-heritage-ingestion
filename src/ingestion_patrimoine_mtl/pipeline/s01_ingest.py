from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import chardet
import pandas as pd
from loguru import logger
from tqdm import tqdm

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.schemas import RawSchema
from ingestion_patrimoine_mtl.utils.hashing import compute_dataframe_hashes

# Sample large enough for reliable detection without reading the whole file.
_ENCODING_SAMPLE_SIZE = 100_000

# Small dataset (~2 700 rows): 500-row chunks give visible progress
# with negligible concatenation overhead.
_CSV_CHUNK_SIZE = 500


def run(cfg: Settings) -> pd.DataFrame:
    """Load the source CSV, hash every row, validate against RawSchema, and write Parquet."""
    _ensure_source_exists(cfg)

    encoding = _detect_encoding(cfg.source_path)
    logger.info(
        "Detected encoding {encoding} for {source}", encoding=encoding, source=cfg.source_path.name
    )

    df = _load_csv(cfg.source_path, encoding)
    df = _strip_column_spaces(df)
    df = _add_row_hashes(df)
    loaded_rows = len(df)
    logger.info("Loaded {rows} rows from {source}", rows=loaded_rows, source=cfg.source_path.name)

    df = _idempotence_filter(df, cfg.stage_01_out)
    skipped_rows = loaded_rows - len(df)
    logger.info(
        "Idempotence filter: {skipped} rows skipped, {new} rows to process",
        skipped=skipped_rows,
        new=len(df),
    )

    df = _add_metadata(df, cfg)
    df = _validate_schema(df)
    _write_parquet(df, cfg.stage_01_out)
    logger.info(
        "Stage 01 complete: {rows} rows written to {path}",
        rows=len(df),
        path=cfg.stage_01_out,
    )
    return df


def _load_csv(path: Path, encoding: str) -> pd.DataFrame:
    """Load the CSV in chunks with a tqdm progress bar.

    Everything is read as ``dtype=str``: ingestion preserves raw fidelity
    (leading zeros on identifiers, years not yet cast); typing is the
    responsibility of the normalize stage.
    """
    chunks: list[pd.DataFrame] = []
    with (
        pd.read_csv(path, encoding=encoding, dtype=str, chunksize=_CSV_CHUNK_SIZE) as reader,
        tqdm(desc=f"Ingestion {path.name}", unit=" rows") as progress,
    ):
        for chunk in reader:
            chunks.append(chunk)
            progress.update(len(chunk))
    if not chunks:
        # Header-only file: re-read without chunks to keep the column names.
        return pd.read_csv(path, encoding=encoding, dtype=str)
    return pd.concat(chunks, ignore_index=True)


def _ensure_source_exists(cfg: Settings) -> None:
    """Fail fast: abort the pipeline if the source CSV is missing."""
    if not cfg.source_path.is_file():
        raise FileNotFoundError(
            f"Source CSV not found: '{cfg.source_path.resolve()}'. "
            "Run `make download` (or `python scripts/download_raw_data.py`) "
            "to fetch the raw data, or adjust INGESTION_RAW_DATA_DIR "
            "/ INGESTION_SOURCE_FILE in your .env."
        )


def _detect_encoding(path: Path) -> str:
    """Detect the encoding of the source file (UTF-8 validated first, chardet fallback)."""
    with path.open("rb") as fh:
        sample = fh.read(_ENCODING_SAMPLE_SIZE)
    try:
        # UTF-8 is self-validating: a successful strict decode is reliable,
        # whereas chardet remains probabilistic on a small sample.
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as exc:
        if exc.start >= len(sample) - 3:
            # Error only on the last bytes: a multi-byte character
            # truncated by sampling, not a false UTF-8 misdetection.
            return "utf-8"
    return chardet.detect(sample).get("encoding") or "latin-1"


def _strip_column_spaces(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from column names (e.g. 'NOM_HISTORIQUE ')."""
    df.columns = df.columns.str.strip()
    return df


def _add_row_hashes(df: pd.DataFrame) -> pd.DataFrame:
    """Compute a deterministic SHA-256 per row and insert it as column record_hash.

    The hash is computed on the raw source columns only, before any pipeline
    metadata columns are appended, so record_hash faithfully reflects the
    content of the original CSV record.
    """
    df = df.copy()
    df["record_hash"] = compute_dataframe_hashes(df)
    return df


def _add_metadata(df: pd.DataFrame, cfg: Settings) -> pd.DataFrame:
    """Append ingested_at (UTC), source_file, and pipeline_version columns."""
    df = df.copy()
    df["ingested_at"] = datetime.now(UTC)
    df["source_file"] = cfg.source_file
    df["pipeline_version"] = cfg.pipeline_version
    return df


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write the validated DataFrame to a snappy-compressed Parquet file.

    The parent directory is created automatically if it does not yet exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


def _validate_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the DataFrame against RawSchema; raises SchemaError on any violation."""
    return RawSchema.validate(df)


def _idempotence_filter(df: pd.DataFrame, previous_out: Path) -> pd.DataFrame:
    """Return only rows whose record_hash is absent from the previous run's output.

    On the first run, when no previous Parquet exists, all rows are returned unchanged.
    """
    if not previous_out.is_file():
        return df
    previous = pd.read_parquet(previous_out, columns=["record_hash"])
    known_hashes: set[str] = set(previous["record_hash"].tolist())
    mask = ~df["record_hash"].isin(known_hashes)
    return df[mask].reset_index(drop=True)
