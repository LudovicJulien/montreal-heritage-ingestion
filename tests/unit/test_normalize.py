"""Unit tests — stage 03 · Normalize."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s03_normalize import (
    _cast_coordinates,
    _cast_years,
    _normalize_est_ouest,
    _normalize_voie_type,
    _validate_arrondissement,
    run,
)
from ingestion_patrimoine_mtl.schemas import NormalizedSchema


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


class TestCastCoordinates:
    def test_coords_inside_bbox_are_kept(self, sample_clean_df: pd.DataFrame) -> None:
        """A Ville-Marie position survives the bbox check."""
        result = _cast_coordinates(sample_clean_df)
        assert result.loc[0, "centro_x"] == pytest.approx(-73.5548)
        assert result.loc[0, "centro_y"] == pytest.approx(45.5019)

    def test_coords_outside_bbox_are_nullified(self, sample_clean_df: pd.DataFrame) -> None:
        """Longitude -100 is nowhere near Montreal."""
        result = _cast_coordinates(sample_clean_df)
        assert pd.isna(result.loc[2, "centro_x"])

    def test_coords_are_nullified_as_a_pair(self, sample_clean_df: pd.DataFrame) -> None:
        """The latitude is valid on its own but useless without the longitude."""
        result = _cast_coordinates(sample_clean_df)
        assert pd.isna(result.loc[2, "centro_y"])

    def test_null_coords_stay_null(self, sample_clean_df: pd.DataFrame) -> None:
        """4.5% of records have no position at all."""
        result = _cast_coordinates(sample_clean_df)
        assert pd.isna(result.loc[3, "centro_x"])
        assert pd.isna(result.loc[3, "centro_y"])

    def test_centro_x_is_the_longitude(self, sample_clean_df: pd.DataFrame) -> None:
        """Guard against the axis swap: centro_x is the longitude, centro_y the latitude."""
        result = _cast_coordinates(sample_clean_df)
        assert (result["centro_x"].dropna() < -70).all()
        assert result["centro_y"].dropna().between(45, 46).all()

    def test_no_row_is_dropped(self, sample_clean_df: pd.DataFrame) -> None:
        """A bad position degrades the field; the building stays in the corpus."""
        result = _cast_coordinates(sample_clean_df)
        assert len(result) == len(sample_clean_df)


class TestValidateArrondissement:
    def test_montreal_suffix_is_stripped(self, sample_clean_df: pd.DataFrame) -> None:
        """The source labels every borough 'X (Montréal)'."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[0, "arrondissement"] == "Ville-Marie"

    def test_em_dash_borough_is_recognized(self, sample_clean_df: pd.DataFrame) -> None:
        """The source em dash is mapped onto the en dash of the official name."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[1, "arrondissement"] == "Rosemont–La Petite-Patrie"

    def test_curly_apostrophe_borough_is_recognized(self, sample_clean_df: pd.DataFrame) -> None:
        """Stage 02 rewrites the apostrophe; matching must survive it."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[2, "arrondissement"] == "L'Île-Bizard–Sainte-Geneviève"

    def test_ville_liee_is_kept_not_rejected(self, sample_clean_df: pd.DataFrame) -> None:
        """Westmount is a valid heritage location, not a data error (ADR-004)."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[3, "arrondissement"] == "Westmount"

    def test_value_outside_agglomeration_is_nullified(self, sample_clean_df: pd.DataFrame) -> None:
        """Laval is outside the agglomeration: the field degrades, the row stays."""
        result = _validate_arrondissement(sample_clean_df)
        assert pd.isna(result.loc[4, "arrondissement"])

    def test_no_row_is_dropped(self, sample_clean_df: pd.DataFrame) -> None:
        """This helper never rejects — only _reject_missing_identifier does."""
        result = _validate_arrondissement(sample_clean_df)
        assert len(result) == len(sample_clean_df)


class TestMunicipaliteType:
    def test_borough_is_tagged_arrondissement(self, sample_clean_df: pd.DataFrame) -> None:
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[0, "municipalite_type"] == "arrondissement"

    def test_em_dash_borough_is_tagged(self, sample_clean_df: pd.DataFrame) -> None:
        """Tagging runs on the canonical form, so spelling variants still resolve."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[1, "municipalite_type"] == "arrondissement"

    def test_curly_apostrophe_borough_is_tagged(self, sample_clean_df: pd.DataFrame) -> None:
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[2, "municipalite_type"] == "arrondissement"

    def test_ville_liee_is_tagged(self, sample_clean_df: pd.DataFrame) -> None:
        """Westmount is kept in the corpus and marked as an independent city."""
        result = _validate_arrondissement(sample_clean_df)
        assert result.loc[3, "municipalite_type"] == "ville_liee"

    def test_unknown_municipality_is_untagged(self, sample_clean_df: pd.DataFrame) -> None:
        """No tag when the municipality resolves to neither list."""
        result = _validate_arrondissement(sample_clean_df)
        assert pd.isna(result.loc[4, "municipalite_type"])

    def test_tagging_counts_split_the_corpus(self, sample_clean_df: pd.DataFrame) -> None:
        """Every row is either a borough, a ville liée, or untagged — nothing is lost."""
        result = _validate_arrondissement(sample_clean_df)
        counts = result["municipalite_type"].value_counts(dropna=False)
        assert counts["arrondissement"] == 4
        assert counts["ville_liee"] == 1


@pytest.fixture
def clean_parquet(cfg: Settings, sample_clean_df: pd.DataFrame) -> Path:
    """Write sample_clean_df to the stage 02 output path run() reads from."""
    cfg.stage_02_out.parent.mkdir(parents=True, exist_ok=True)
    sample_clean_df.to_parquet(cfg.stage_02_out, index=False)
    return Path(cfg.stage_02_out)


class TestRunNormalize:
    def test_row_without_identifier_is_rejected(self, cfg: Settings, clean_parquet: Path) -> None:
        """The one rejection ADR-004 allows: a record with no identity."""
        result = run(cfg)
        assert len(result) == 5

    def test_every_output_row_has_an_identifier(self, cfg: Settings, clean_parquet: Path) -> None:
        """After rejection the identifier is non-null by construction."""
        result = run(cfg)
        assert result["identifiant_batiment"].notna().all()

    def test_only_the_identity_less_row_is_dropped(
        self, cfg: Settings, clean_parquet: Path
    ) -> None:
        """The row with a bad borough, a bad year and bad coords all survive."""
        result = run(cfg)
        assert set(result["record_hash"]) == {"a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64}

    def test_parquet_written_to_expected_path(self, cfg: Settings, clean_parquet: Path) -> None:
        """run() creates the Parquet file at the path returned by cfg.stage_03_out."""
        run(cfg)
        assert cfg.stage_03_out.is_file()

    def test_written_parquet_passes_schema_validation(
        self, cfg: Settings, clean_parquet: Path
    ) -> None:
        """What lands on disk satisfies the contract, not just what run() returns."""
        run(cfg)
        NormalizedSchema.validate(pd.read_parquet(cfg.stage_03_out))

    def test_written_parquet_carries_municipalite_type(
        self, cfg: Settings, clean_parquet: Path
    ) -> None:
        """The scope tag survives the Parquet round-trip to the next stage."""
        run(cfg)
        df = pd.read_parquet(cfg.stage_03_out)
        assert "municipalite_type" in df.columns
        assert set(df["municipalite_type"].dropna()) == {"arrondissement", "ville_liee"}

    def test_years_round_trip_as_nullable_integers(
        self, cfg: Settings, clean_parquet: Path
    ) -> None:
        """Int64 survives Parquet — a float round-trip would print years as 1846.0."""
        run(cfg)
        df = pd.read_parquet(cfg.stage_03_out)
        assert str(df["debut_des_travaux"].dtype) == "Int64"
