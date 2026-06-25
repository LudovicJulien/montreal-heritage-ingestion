from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s01_ingest import (
    _detect_encoding,
    _idempotence_filter,
    _strip_column_spaces,
    run,
)
from ingestion_patrimoine_mtl.schemas import RawSchema


class TestDetectEncoding:
    def test_utf8_file_returns_utf8(self, tmp_path: Path) -> None:
        """A well-formed UTF-8 file with French accents is detected as UTF-8."""
        csv_file = tmp_path / "sample.csv"
        csv_file.write_bytes("no_batiment,nom_historique\n0001,Édifice Art déco\n".encode())
        assert _detect_encoding(csv_file) == "utf-8"

    def test_latin1_file_not_detected_as_utf8(self, tmp_path: Path) -> None:
        """A latin-1 file containing bytes invalid in UTF-8 is not reported as UTF-8."""
        csv_file = tmp_path / "sample.csv"
        # Repeat enough content for chardet to identify the encoding confidently.
        content = "nom,adresse\n" + "Café de Paris,Montréal\n" * 50
        csv_file.write_bytes(content.encode("latin-1"))
        assert _detect_encoding(csv_file) != "utf-8"

    def test_latin1_detected_encoding_decodes_content(self, tmp_path: Path) -> None:
        """The encoding returned for a latin-1 file correctly round-trips its content."""
        original = "nom,adresse\n" + "Hôtel de Ville,Montréal\n" * 50
        csv_file = tmp_path / "sample.csv"
        csv_file.write_bytes(original.encode("latin-1"))
        encoding = _detect_encoding(csv_file)
        decoded = csv_file.read_bytes().decode(encoding)
        assert "H" in decoded and "Montr" in decoded


class TestStripColumnSpaces:
    def test_trailing_whitespace_stripped(self) -> None:
        """Column names with trailing spaces are stripped to their clean form."""
        df = pd.DataFrame({"NOM_HISTORIQUE ": [1], "ADRESSE ": [2]})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM_HISTORIQUE", "ADRESSE"]

    def test_leading_whitespace_stripped(self) -> None:
        """Column names with leading spaces are stripped to their clean form."""
        df = pd.DataFrame({" NOM_HISTORIQUE": [1], " ADRESSE": [2]})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM_HISTORIQUE", "ADRESSE"]

    def test_leading_and_trailing_whitespace_stripped(self) -> None:
        """Column names with both leading and trailing spaces are fully stripped."""
        df = pd.DataFrame({"  NOM_HISTORIQUE  ": [1]})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM_HISTORIQUE"]

    def test_clean_column_names_unchanged(self) -> None:
        """Column names without surrounding whitespace pass through untouched."""
        df = pd.DataFrame({"NOM_HISTORIQUE": [1], "ADRESSE": [2]})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM_HISTORIQUE", "ADRESSE"]

    def test_empty_dataframe_columns_stripped(self) -> None:
        """Column names are stripped even when the DataFrame contains no rows."""
        df = pd.DataFrame({"NOM ": pd.Series([], dtype=str), " ADRESSE": pd.Series([], dtype=str)})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM", "ADRESSE"]
        assert len(result) == 0

    def test_internal_whitespace_preserved(self) -> None:
        """Spaces inside a column name are not removed — only leading/trailing ones are."""
        df = pd.DataFrame({" NOM HISTORIQUE ": [1]})
        result = _strip_column_spaces(df)
        assert list(result.columns) == ["NOM HISTORIQUE"]


def _make_df(*hashes: str) -> pd.DataFrame:
    """Build a minimal DataFrame with a record_hash column for idempotence tests."""
    return pd.DataFrame({"record_hash": list(hashes), "value": range(len(hashes))})


class TestIdempotenceFilter:
    def test_no_previous_parquet_returns_all_rows(self, tmp_path: Path) -> None:
        """On first run (no previous output), every row is returned unchanged."""
        df = _make_df("aaa", "bbb", "ccc")
        result = _idempotence_filter(df, tmp_path / "nonexistent.parquet")
        assert len(result) == 3
        assert list(result["record_hash"]) == ["aaa", "bbb", "ccc"]

    def test_all_hashes_known_returns_empty(self, tmp_path: Path) -> None:
        """When every row was already processed, the filter returns an empty DataFrame."""
        previous = pd.DataFrame({"record_hash": ["aaa", "bbb"]})
        parquet_path = tmp_path / "previous.parquet"
        previous.to_parquet(parquet_path, index=False)

        df = _make_df("aaa", "bbb")
        result = _idempotence_filter(df, parquet_path)
        assert len(result) == 0

    def test_partial_overlap_returns_only_new_rows(self, tmp_path: Path) -> None:
        """Only rows whose hash is absent from the previous output are kept."""
        previous = pd.DataFrame({"record_hash": ["aaa", "bbb"]})
        parquet_path = tmp_path / "previous.parquet"
        previous.to_parquet(parquet_path, index=False)

        df = _make_df("aaa", "bbb", "ccc", "ddd")
        result = _idempotence_filter(df, parquet_path)
        assert list(result["record_hash"]) == ["ccc", "ddd"]

    def test_no_hash_overlap_returns_all_rows(self, tmp_path: Path) -> None:
        """When no row matches the previous output, the entire DataFrame is returned."""
        previous = pd.DataFrame({"record_hash": ["xxx", "yyy"]})
        parquet_path = tmp_path / "previous.parquet"
        previous.to_parquet(parquet_path, index=False)

        df = _make_df("aaa", "bbb")
        result = _idempotence_filter(df, parquet_path)
        assert list(result["record_hash"]) == ["aaa", "bbb"]

    def test_filtered_result_has_reset_index(self, tmp_path: Path) -> None:
        """The returned DataFrame always has a clean 0-based integer index."""
        previous = pd.DataFrame({"record_hash": ["aaa"]})
        parquet_path = tmp_path / "previous.parquet"
        previous.to_parquet(parquet_path, index=False)

        df = _make_df("aaa", "bbb", "ccc")
        result = _idempotence_filter(df, parquet_path)
        assert list(result.index) == list(range(len(result)))


@pytest.fixture
def source_csv(cfg: Settings, sample_raw_df: pd.DataFrame) -> Path:
    """Write sample_raw_df as a CSV to the configured source path and return it."""
    cfg.source_path.parent.mkdir(parents=True, exist_ok=True)
    sample_raw_df.to_csv(cfg.source_path, index=False)
    return Path(cfg.source_path)


class TestRunIngest:
    def test_parquet_written_to_expected_path(self, cfg: Settings, source_csv: Path) -> None:
        """run() creates the Parquet file at the path returned by cfg.stage_01_out."""
        run(cfg)
        assert cfg.stage_01_out.is_file()

    def test_parquet_passes_raw_schema_validation(self, cfg: Settings, source_csv: Path) -> None:
        """The output Parquet satisfies all RawSchema constraints, including hash length."""
        run(cfg)
        df = pd.read_parquet(cfg.stage_01_out)
        RawSchema.validate(df)

    def test_parquet_row_count_matches_source(self, cfg: Settings, source_csv: Path) -> None:
        """All source records appear in the output — no rows are silently dropped."""
        run(cfg)
        result = pd.read_parquet(cfg.stage_01_out)
        source = pd.read_csv(source_csv, dtype=str)
        assert len(result) == len(source)

    def test_metadata_columns_are_non_null(self, cfg: Settings, source_csv: Path) -> None:
        """ingested_at, source_file, and pipeline_version are populated for every row."""
        run(cfg)
        df = pd.read_parquet(cfg.stage_01_out)
        for col in ("ingested_at", "source_file", "pipeline_version"):
            assert col in df.columns, f"missing column: {col}"
            assert df[col].notna().all(), f"null values found in column: {col}"
