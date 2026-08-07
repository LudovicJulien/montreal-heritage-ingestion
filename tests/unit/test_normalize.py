"""Unit tests — stage 03 · Normalize."""

from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.pipeline.s03_normalize import (
    _cast_years,
    _normalize_est_ouest,
    _normalize_voie_type,
)


class TestNormalizeVoieType:
    def test_cased_value_becomes_lowercase(self, sample_clean_df: pd.DataFrame) -> None:
        """'Avenue' collapses onto 'avenue' — the only casing collision in the source."""
        result = _normalize_voie_type(sample_clean_df)
        assert result.loc[1, "type_de_voie"] == "avenue"

    def test_already_lowercase_is_unchanged(self, sample_clean_df: pd.DataFrame) -> None:
        """A value already in canonical form passes through untouched."""
        result = _normalize_voie_type(sample_clean_df)
        assert result.loc[0, "type_de_voie"] == "rue"

    def test_null_stays_null(self, sample_clean_df: pd.DataFrame) -> None:
        """A missing street type is not imputed."""
        result = _normalize_voie_type(sample_clean_df)
        assert pd.isna(result.loc[2, "type_de_voie"])

    def test_source_dataframe_is_not_mutated(self, sample_clean_df: pd.DataFrame) -> None:
        """The helper returns a copy — the caller's frame is left alone."""
        _normalize_voie_type(sample_clean_df)
        assert sample_clean_df.loc[1, "type_de_voie"] == "Avenue"


class TestNormalizeEstOuest:
    def test_canonical_value_passes_through(self, sample_clean_df: pd.DataFrame) -> None:
        """'Est' is already canonical and is returned unchanged."""
        result = _normalize_est_ouest(sample_clean_df)
        assert result.loc[0, "est_ouest"] == "Est"

    def test_abbreviation_is_expanded(self, sample_clean_df: pd.DataFrame) -> None:
        """'O' maps to 'Ouest' — absent from this extract, kept as a refresh guard."""
        result = _normalize_est_ouest(sample_clean_df)
        assert result.loc[1, "est_ouest"] == "Ouest"

    def test_unexpected_value_is_nullified(self, sample_clean_df: pd.DataFrame) -> None:
        """'Nord' is not a cardinal the source uses, so the field degrades to null."""
        result = _normalize_est_ouest(sample_clean_df)
        assert pd.isna(result.loc[2, "est_ouest"])

    def test_unexpected_value_does_not_raise(self, sample_clean_df: pd.DataFrame) -> None:
        """A bad value degrades the field, it never aborts the run (ADR-004)."""
        result = _normalize_est_ouest(sample_clean_df)
        assert len(result) == len(sample_clean_df)

    def test_none_stays_none(self, sample_clean_df: pd.DataFrame) -> None:
        """A missing cardinal is normal — 61% of records have none."""
        result = _normalize_est_ouest(sample_clean_df)
        assert pd.isna(result.loc[3, "est_ouest"])


class TestCastYears:
    def test_valid_year_is_kept(self, sample_clean_df: pd.DataFrame) -> None:
        """A plausible year survives the cast unchanged."""
        result = _cast_years(sample_clean_df)
        assert result.loc[0, "debut_des_travaux"] == 1846

    def test_9999_sentinel_is_nullified(self, sample_clean_df: pd.DataFrame) -> None:
        """9999 is the source's 'unknown', not a year."""
        result = _cast_years(sample_clean_df)
        assert pd.isna(result.loc[1, "debut_des_travaux"])

    def test_zero_sentinel_is_nullified(self, sample_clean_df: pd.DataFrame) -> None:
        """0 is the other 'unknown' sentinel — 242 records carry it on fin_des_travaux."""
        result = _cast_years(sample_clean_df)
        assert pd.isna(result.loc[2, "debut_des_travaux"])

    def test_out_of_range_year_is_nullified_not_clamped(
        self, sample_clean_df: pd.DataFrame
    ) -> None:
        """2500 becomes null, never 2030 — clamping would fabricate a date (ADR-004)."""
        result = _cast_years(sample_clean_df)
        assert pd.isna(result.loc[3, "fin_des_travaux"])

    def test_dtype_is_nullable_integer(self, sample_clean_df: pd.DataFrame) -> None:
        """Years are integers that can be absent, so Int64 rather than float or int."""
        result = _cast_years(sample_clean_df)
        assert str(result["debut_des_travaux"].dtype) == "Int64"
