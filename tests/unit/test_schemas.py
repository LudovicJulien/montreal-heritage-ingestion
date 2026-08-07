"""Unit tests — Pandera schemas."""

from __future__ import annotations

import pandas as pd
import pandera
import pytest

from ingestion_patrimoine_mtl.schemas import CleanSchema, NormalizedSchema


class TestCleanSchema:
    def _valid_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "identifiant_batiment": ["0039-27-4599-00"],
                "nom_historique": ["Maison Dupont"],
                "voie": ["McGill"],
                "arrondissement": ["Ville-Marie"],
                "record_hash": ["a" * 64],
            }
        )

    def test_valid_dataframe_passes(self) -> None:
        CleanSchema.validate(self._valid_df())

    def test_null_source_columns_are_accepted(self) -> None:
        df = self._valid_df().copy()
        df["identifiant_batiment"] = None
        df["nom_historique"] = None
        CleanSchema.validate(df)

    def test_missing_record_hash_raises(self) -> None:
        df = self._valid_df().drop(columns=["record_hash"])
        with pytest.raises(pandera.errors.SchemaError):
            CleanSchema.validate(df)

    def test_short_record_hash_raises(self) -> None:
        df = self._valid_df().copy()
        df["record_hash"] = "tooshort"
        with pytest.raises(pandera.errors.SchemaError):
            CleanSchema.validate(df)

    def test_extra_columns_are_accepted(self) -> None:
        df = self._valid_df().copy()
        df["ingested_at"] = pd.Timestamp("2026-06-01")
        CleanSchema.validate(df)


class TestRawSchema:
    @pytest.mark.skip(reason="implement with s01_ingest")
    def test_valid_dataframe_passes(self) -> None: ...

    @pytest.mark.skip(reason="implement with s01_ingest")
    def test_missing_record_hash_raises(self) -> None: ...

    @pytest.mark.skip(reason="implement with s01_ingest")
    def test_wrong_hash_length_raises(self) -> None: ...


class TestNormalizedSchema:
    def _valid_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "identifiant_batiment": ["0039-27-4599-00"],
                "nom_historique": ["Maison Dupont"],
                "voie": ["McGill"],
                "arrondissement": ["Ville-Marie"],
                "municipalite_type": ["arrondissement"],
                "centro_x": [-73.5548],
                "centro_y": [45.5019],
                "record_hash": ["a" * 64],
            }
        )

    def test_valid_dataframe_passes(self) -> None:
        NormalizedSchema.validate(self._valid_df())

    def test_nullable_coords_are_accepted(self) -> None:
        """4.5% of buildings have no position at all."""
        df = self._valid_df()
        df["centro_x"] = None
        df["centro_y"] = None
        NormalizedSchema.validate(df)

    def test_longitude_outside_bbox_raises(self) -> None:
        """Stage 03 nullifies these, so reaching the schema means the stage failed."""
        df = self._valid_df()
        df["centro_x"] = -100.0
        with pytest.raises(pandera.errors.SchemaError):
            NormalizedSchema.validate(df)

    def test_latitude_outside_bbox_raises(self) -> None:
        df = self._valid_df()
        df["centro_y"] = 43.65
        with pytest.raises(pandera.errors.SchemaError):
            NormalizedSchema.validate(df)

    def test_ville_liee_is_accepted(self) -> None:
        """The allowlist spans the whole agglomeration, not just the 19 boroughs."""
        df = self._valid_df()
        df["arrondissement"] = "Westmount"
        df["municipalite_type"] = "ville_liee"
        NormalizedSchema.validate(df)

    def test_municipality_outside_the_allowlist_raises(self) -> None:
        """Stage 03 nullifies unknown municipalities before this point."""
        df = self._valid_df()
        df["arrondissement"] = "Laval"
        with pytest.raises(pandera.errors.SchemaError):
            NormalizedSchema.validate(df)

    def test_unknown_municipalite_type_raises(self) -> None:
        df = self._valid_df()
        df["municipalite_type"] = "banlieue"
        with pytest.raises(pandera.errors.SchemaError):
            NormalizedSchema.validate(df)

    def test_null_identifier_raises(self) -> None:
        """Stage 03 rejects those rows, so the column is non-null by construction."""
        df = self._valid_df()
        df["identifiant_batiment"] = None
        with pytest.raises(pandera.errors.SchemaError):
            NormalizedSchema.validate(df)
