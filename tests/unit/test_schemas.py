"""Unit tests — Pandera schemas."""

from __future__ import annotations

import pandas as pd
import pandera
import pytest

from ingestion_patrimoine_mtl.schemas import CleanSchema


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
    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_coords_outside_bbox_raises(self) -> None: ...

    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_nullable_coords_are_accepted(self) -> None: ...
