"""Unit tests — stage 01b · RPCQ open data ingest."""

from __future__ import annotations

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s01b_rpcq import (
    CITES_LAYOUT,
    CLASSES_LAYOUT,
    RPCQ_COLUMNS,
    _extract_coordinates,
    _filter_montreal_region,
    _load_exports,
    _normalize_column_names,
    _prepare_export,
    _reconcile_columns,
    _tag_protection_regime,
)
from ingestion_patrimoine_mtl.schemas import REGIME_CITE, REGIME_CLASSE


class TestNormalizeColumnNames:
    def test_mixed_case_export_columns_lowercased(self) -> None:
        """The classés export mixes cases in one header row; every name is lowercased."""
        df = pd.DataFrame({"nom_bien": [1], "Wkt_Multipoint_XY": [2]})
        assert list(_normalize_column_names(df).columns) == ["nom_bien", "wkt_multipoint_xy"]

    def test_surrounding_whitespace_stripped(self) -> None:
        """Names are stripped before lowercasing, as in stage 01."""
        df = pd.DataFrame({" bien_id ": [1]})
        assert list(_normalize_column_names(df).columns) == ["bien_id"]


class TestLoadExports:
    def test_both_exports_are_merged_into_one_frame(self, rpcq_exports: Settings) -> None:
        """The merged frame holds every record of both exports, before any filtering."""
        df = _load_exports(rpcq_exports)
        assert len(df) == 7

    def test_merged_frame_uses_the_reconciled_column_set(self, rpcq_exports: Settings) -> None:
        """Both exports are aligned on RPCQ_COLUMNS, so the concatenation stays rectangular."""
        df = _load_exports(rpcq_exports)
        assert list(df.columns) == RPCQ_COLUMNS

    def test_export_specific_columns_are_dropped(self, rpcq_exports: Settings) -> None:
        """Columns outside the reconciled set — geometries, version — do not survive."""
        df = _load_exports(rpcq_exports)
        for column in ("version", "terrain_protege_situation", "geometrie", "wkt_multipoint_xy"):
            assert column not in df.columns

    def test_utf8_bom_of_the_classes_export_is_stripped(self, rpcq_exports: Settings) -> None:
        """The BOM would otherwise turn the first column into '\\ufeffnom_bien'."""
        df = _load_exports(rpcq_exports)
        assert df["nom_bien"].notna().all()


class TestReconcileColumns:
    def test_cites_year_columns_are_renamed(self, rpcq_exports: Settings) -> None:
        """'de' and 'a' become debut_construction and fin_construction."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert df.loc[0, "debut_construction"] == "1817"
        assert df.loc[0, "fin_construction"] == "1817"

    def test_approximate_years_survive_as_text(self, rpcq_exports: Settings) -> None:
        """'vers 1840' is preserved verbatim — casting here would nullify it."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert df.loc[1, "debut_construction"] == "vers 1840"

    def test_autorite_is_renamed_to_autorite_protection(self, rpcq_exports: Settings) -> None:
        """The cités 'autorite' column lands on the classés name."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert df.loc[0, "autorite_protection"] == "Municipalité"

    def test_classes_status_column_is_renamed(self, rpcq_exports: Settings) -> None:
        """'statut_juridique_princ' lands on the canonical 'statut_juridique'."""
        df = _prepare_export(rpcq_exports.rpcq_classes_path, CLASSES_LAYOUT)
        assert df.loc[0, "statut_juridique"] == "Classement"

    def test_columns_absent_from_an_export_are_materialised_as_null(self) -> None:
        """reindex creates the missing canonical columns rather than leaving them out."""
        df = pd.DataFrame({"bien_id": ["92513"], "regime_protection": [REGIME_CLASSE]})
        result = _reconcile_columns(df, {})
        assert list(result.columns) == RPCQ_COLUMNS
        assert pd.isna(result.loc[0, "url_rpcq"])


class TestExtractCoordinates:
    def test_wkt_yields_longitude_then_latitude(self) -> None:
        """The WKT axis order is X then Y: the first number is the longitude."""
        df = pd.DataFrame({"wkt_multipoint_xy": ["MULTIPOINT ((-73.554973 45.500323))"]})
        result = _extract_coordinates(df)
        assert result.loc[0, "longitude"] == pytest.approx(-73.554973)
        assert result.loc[0, "latitude"] == pytest.approx(45.500323)

    def test_first_point_of_a_multipoint_is_kept(self) -> None:
        """A bien with several points keeps the first, the one the RPCQ displays."""
        wkt = "MULTIPOINT ((-73.596000 45.487000),(-73.595500 45.486800))"
        result = _extract_coordinates(pd.DataFrame({"wkt_multipoint_xy": [wkt]}))
        assert result.loc[0, "longitude"] == pytest.approx(-73.596)

    def test_unparsable_wkt_yields_null_coordinates(self) -> None:
        """A geometry that does not parse degrades to null instead of raising."""
        result = _extract_coordinates(pd.DataFrame({"wkt_multipoint_xy": ["EMPTY"]}))
        assert pd.isna(result.loc[0, "latitude"])
        assert pd.isna(result.loc[0, "longitude"])

    def test_published_coordinates_are_cast_without_a_wkt_column(self) -> None:
        """The cités layout has no WKT column; its own coordinates still become floats."""
        df = pd.DataFrame({"latitude": ["45.5"], "longitude": ["-73.5"]})
        result = _extract_coordinates(df)
        assert result.loc[0, "latitude"] == pytest.approx(45.5)

    def test_a_published_coordinate_wins_over_the_geometry(self) -> None:
        """Where both exist the published pair is authoritative; the WKT fills gaps."""
        df = pd.DataFrame(
            {
                "latitude": ["45.5"],
                "longitude": ["-73.5"],
                "wkt_multipoint_xy": ["MULTIPOINT ((-71.2 46.8))"],
            }
        )
        result = _extract_coordinates(df)
        assert result.loc[0, "latitude"] == pytest.approx(45.5)

    def test_cites_coordinates_are_read_as_floats(self, rpcq_exports: Settings) -> None:
        """The published latitude/longitude strings are usable as numbers downstream."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert df.loc[0, "latitude"] == pytest.approx(45.412944)

    def test_missing_cites_coordinates_stay_null(self, rpcq_exports: Settings) -> None:
        """76 cited records carry no position; they are kept with null coordinates."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert pd.isna(df.loc[1, "latitude"])


class TestFilterMontrealRegion:
    def test_out_of_region_records_are_dropped(self, rpcq_exports: Settings) -> None:
        """Records from other administrative regions do not reach the output."""
        df = _filter_montreal_region(_load_exports(rpcq_exports))
        assert set(df["region_admin"]) == {"Montréal"}
        assert len(df) == 5

    def test_villes_liees_are_kept(self, rpcq_exports: Settings) -> None:
        """The filter is on the region, so Baie-D'Urfé and Beaconsfield survive.

        Filtering on municipalite == 'Montréal' would drop them, along with every
        other ville liée of the agglomeration the Données Montréal corpus covers.
        """
        df = _filter_montreal_region(_load_exports(rpcq_exports))
        assert {"Baie-D'Urfé", "Beaconsfield"} <= set(df["municipalite"])

    def test_index_is_reset(self, rpcq_exports: Settings) -> None:
        """The filtered frame is re-indexed contiguously from zero."""
        df = _filter_montreal_region(_load_exports(rpcq_exports))
        assert list(df.index) == list(range(len(df)))


class TestTagProtectionRegime:
    def test_classes_export_is_tagged_classe(self, rpcq_exports: Settings) -> None:
        """Every row read from the classés export carries regime_protection == 'classe'."""
        df = _prepare_export(rpcq_exports.rpcq_classes_path, CLASSES_LAYOUT)
        assert set(df["regime_protection"]) == {REGIME_CLASSE}

    def test_cites_export_is_tagged_cite(self, rpcq_exports: Settings) -> None:
        """Every row read from the cités export carries regime_protection == 'cite'."""
        df = _prepare_export(rpcq_exports.rpcq_cites_path, CITES_LAYOUT)
        assert set(df["regime_protection"]) == {REGIME_CITE}

    def test_a_bien_in_both_exports_keeps_one_row_per_regime(self, rpcq_exports: Settings) -> None:
        """A doubly-protected bien stays as two distinguishable rows, not a duplicate."""
        df = _load_exports(rpcq_exports)
        both = df[df["bien_id"] == "93001"]
        assert len(both) == 2
        assert set(both["regime_protection"]) == {REGIME_CLASSE, REGIME_CITE}

    def test_regime_is_added_without_touching_the_caller_frame(self) -> None:
        """Tagging returns a copy; the input frame is left unmodified."""
        df = pd.DataFrame({"bien_id": ["1"]})
        _tag_protection_regime(df, REGIME_CLASSE)
        assert "regime_protection" not in df.columns
