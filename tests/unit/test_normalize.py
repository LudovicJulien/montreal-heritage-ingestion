"""Unit tests — stage 03 · Normalize."""

from __future__ import annotations

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.pipeline.s03_normalize import _normalize_voie_type


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
    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_e_becomes_est(self) -> None: ...

    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_o_becomes_ouest(self) -> None: ...

    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_none_stays_none(self) -> None: ...


class TestCastYears:
    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_valid_year_is_kept(self) -> None: ...

    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_year_out_of_range_is_nullified(self) -> None: ...
