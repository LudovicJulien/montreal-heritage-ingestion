"""Unit tests — Pandera schemas."""

from __future__ import annotations

import pandas as pd
import pandera
import pytest

from ingestion_patrimoine_mtl.schemas import (
    REGIME_CITE,
    REGIME_CLASSE,
    CleanSchema,
    NormalizedSchema,
    RpcqRawSchema,
)


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


class TestRpcqRawSchema:
    def _valid_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bien_id": ["92513"],
                "url_rpcq": ["http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=92513"],
                "nom_bien": ["Maisons-magasins Jacob-De Witt I"],
                "statut_juridique": ["Classement"],
                "regime_protection": [REGIME_CLASSE],
                "municipalite": ["Montréal"],
                "latitude": [45.500323],
                "longitude": [-73.554973],
                "record_hash": ["a" * 64],
                "ingested_at": [pd.Timestamp("2026-08-24", tz="UTC")],
                "source_file": ["immeubles_classes.csv"],
                "pipeline_version": ["0.4.0"],
            }
        )

    def test_valid_dataframe_passes(self) -> None:
        RpcqRawSchema.validate(self._valid_df())

    def test_missing_bien_id_raises(self) -> None:
        df = self._valid_df().drop(columns=["bien_id"])
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)

    def test_null_bien_id_raises(self) -> None:
        df = self._valid_df().copy()
        df["bien_id"] = None
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)

    def test_null_coordinates_are_accepted(self) -> None:
        """2 of the 179 Montreal records carry no position; they stay in the corpus."""
        df = self._valid_df().copy()
        df["latitude"] = None
        df["longitude"] = None
        RpcqRawSchema.validate(df)

    def test_coordinates_outside_the_montreal_box_raise(self) -> None:
        """A latitude from the Capitale-Nationale region means the filter let a row through."""
        df = self._valid_df().copy()
        df["latitude"] = 46.813
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)

    def test_swapped_coordinates_raise(self) -> None:
        """Latitude and longitude do not overlap, so an axis swap fails the schema."""
        df = self._valid_df().copy()
        df["latitude"], df["longitude"] = -73.554973, 45.500323
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)

    def test_unknown_protection_regime_raises(self) -> None:
        df = self._valid_df().copy()
        df["regime_protection"] = "inscrit"
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)

    def test_citation_regime_passes(self) -> None:
        df = self._valid_df().copy()
        df["regime_protection"] = REGIME_CITE
        df["statut_juridique"] = "Citation"
        RpcqRawSchema.validate(df)

    def test_unlisted_legal_status_is_accepted(self) -> None:
        """The classés export already holds an 'Avis d'intention' — no allowlist here."""
        df = self._valid_df().copy()
        df["statut_juridique"] = "Avis d'intention de classement prorogé"
        RpcqRawSchema.validate(df)

    def test_short_record_hash_raises(self) -> None:
        df = self._valid_df().copy()
        df["record_hash"] = "tooshort"
        with pytest.raises(pandera.errors.SchemaError):
            RpcqRawSchema.validate(df)


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

    def test_null_nom_historique_is_accepted(self) -> None:
        """30 buildings have no historical name — the record is still valid."""
        df = self._valid_df()
        df["nom_historique"] = None
        NormalizedSchema.validate(df)

    def test_null_voie_is_accepted(self) -> None:
        """37 buildings have no street — nullified, not rejected (ADR-004)."""
        df = self._valid_df()
        df["voie"] = None
        NormalizedSchema.validate(df)

    def test_null_arrondissement_is_accepted(self) -> None:
        """An unrecognized municipality is nullified upstream and must pass here."""
        df = self._valid_df()
        df["arrondissement"] = None
        df["municipalite_type"] = None
        NormalizedSchema.validate(df)
