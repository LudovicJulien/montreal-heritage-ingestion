"""Unit tests — stage 02 · Clean."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pandera
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline import s02_clean
from ingestion_patrimoine_mtl.pipeline.s02_clean import (
    _collapse_whitespace,
    _empty_to_none,
    _fix_encoding,
    _normalize_french_typography,
    _strip_html,
    _validate_schema,
    _write_parquet,
)


class TestStripHtml:
    def test_removes_italic_tags(self) -> None:
        assert _strip_html("<i>dry goods</i> store") == "dry goods store"

    def test_decodes_html_entities(self) -> None:
        assert _strip_html("Siège de l&#39;administration") == "Siège de l'administration"

    def test_returns_none_for_none_input(self) -> None:
        assert _strip_html(None) is None

    def test_collapses_whitespace_after_strip(self) -> None:
        assert _strip_html("<p>Line one</p><p>Line two</p>") == "Line one Line two"

    def test_unwraps_superscript_inline(self) -> None:
        assert _strip_html("M<sup>e</sup> Dupont") == "Me Dupont"

    def test_unwraps_subscript_inline(self) -> None:
        assert _strip_html("H<sub>2</sub>O") == "H2O"


class TestFixEncoding:
    def test_fixes_mojibake(self) -> None:
        # "é" encoded as UTF-8 then misread as Latin-1: \xc3\xa9 → "Ã©"
        assert _fix_encoding("Ã©difice") == "édifice"

    def test_no_op_on_clean_text(self) -> None:
        assert _fix_encoding("édifice patrimonial") == "édifice patrimonial"

    def test_no_op_on_ascii(self) -> None:
        assert _fix_encoding("heritage building") == "heritage building"

    def test_returns_none_for_none_input(self) -> None:
        assert _fix_encoding(None) is None

    def test_returns_none_for_pandas_na(self) -> None:
        from typing import Any

        import pandas as pd

        na: Any = pd.NA
        assert _fix_encoding(na) is None

    def test_fixes_double_mojibake(self) -> None:
        # "é" double-encoded: UTF-8 bytes misread twice → "Ã\x83Â©"
        assert _fix_encoding("Ã\x83Â©difice") == "édifice"


class TestCollapseWhitespace:
    def test_collapses_multiple_spaces(self) -> None:
        assert _collapse_whitespace("foo  bar") == "foo bar"

    def test_collapses_newlines(self) -> None:
        assert _collapse_whitespace("foo\nbar") == "foo bar"

    def test_collapses_tabs(self) -> None:
        assert _collapse_whitespace("foo\tbar") == "foo bar"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert _collapse_whitespace("  foo bar  ") == "foo bar"

    def test_no_op_on_clean_text(self) -> None:
        assert _collapse_whitespace("édifice patrimonial") == "édifice patrimonial"

    def test_returns_none_for_none_input(self) -> None:
        assert _collapse_whitespace(None) is None


class TestEmptyToNone:
    def test_converts_empty_string_to_na(self) -> None:
        df = pd.DataFrame({"nom": ["", "Maison Dupont"]})
        result = _empty_to_none(df)
        assert result["nom"].iloc[0] is pd.NA
        assert result["nom"].iloc[1] == "Maison Dupont"

    def test_converts_all_object_columns(self) -> None:
        df = pd.DataFrame({"a": ["", "x"], "b": ["y", ""]})
        result = _empty_to_none(df)
        assert result["a"].iloc[0] is pd.NA
        assert result["b"].iloc[1] is pd.NA

    def test_leaves_non_object_columns_untouched(self) -> None:
        df = pd.DataFrame({"nom": [""], "annee": [0]})
        result = _empty_to_none(df)
        assert result["annee"].iloc[0] == 0

    def test_preserves_existing_nulls(self) -> None:
        df = pd.DataFrame({"nom": [None, "x"]})
        result = _empty_to_none(df)
        assert result["nom"].iloc[0] is None

    def test_whitespace_only_cells_not_converted(self) -> None:
        # _empty_to_none only targets exact '' — whitespace is _collapse_whitespace's job
        df = pd.DataFrame({"nom": ["   "]})
        result = _empty_to_none(df)
        assert result["nom"].iloc[0] == "   "

    def test_does_not_mutate_input(self) -> None:
        df = pd.DataFrame({"nom": [""]})
        _empty_to_none(df)
        assert df["nom"].iloc[0] == ""


class TestNormalizeFrenchTypography:
    def test_replaces_straight_apostrophes(self) -> None:
        assert _normalize_french_typography("l'église") == "l’église"

    def test_no_op_on_none(self) -> None:
        assert _normalize_french_typography(None) is None

    def test_multiple_apostrophes(self) -> None:
        result = _normalize_french_typography("l'église d'aujourd'hui")
        assert result == "l’église d’aujourd’hui"

    def test_converts_ascii_double_quotes_to_guillemets(self) -> None:
        result = _normalize_french_typography('"Maison Dupont"')
        assert result == "« Maison Dupont »"

    def test_no_op_on_curly_apostrophe(self) -> None:
        # Already correct — straight-replace does not affect U+2019
        assert _normalize_french_typography("l’église") == "l’église"

    def test_no_op_on_text_without_special_chars(self) -> None:
        text = "Édifice patrimonial construit en 1846."
        assert _normalize_french_typography(text) == text


class TestWriteParquet:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"nom": ["Maison Dupont", "Église Saint-Patrick"], "annee": [1846, 1843]}
        )

    def test_creates_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "02_clean" / "buildings_clean.parquet"
        _write_parquet(self._sample_df(), dest)
        assert dest.is_file()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        dest = tmp_path / "nested" / "deep" / "output.parquet"
        _write_parquet(self._sample_df(), dest)
        assert dest.is_file()

    def test_roundtrip_preserves_data(self, tmp_path: Path) -> None:
        dest = tmp_path / "output.parquet"
        original = self._sample_df()
        _write_parquet(original, dest)
        reloaded = pd.read_parquet(dest)
        pd.testing.assert_frame_equal(original, reloaded)

    def test_uses_snappy_compression(self, tmp_path: Path) -> None:
        dest = tmp_path / "output.parquet"
        _write_parquet(self._sample_df(), dest)
        import pyarrow.parquet as pq

        pf = pq.read_metadata(dest)
        assert pf.row_group(0).column(0).compression == "SNAPPY"


class TestValidateSchema:
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

    def test_valid_df_returns_dataframe(self) -> None:
        result = _validate_schema(self._valid_df())
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_missing_record_hash_raises(self) -> None:
        df = self._valid_df().drop(columns=["record_hash"])
        with pytest.raises(pandera.errors.SchemaError):
            _validate_schema(df)


class TestRun:
    @pytest.fixture
    def stage01_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "identifiant_batiment": [
                    "0039-27-4599-00",
                    "0039-27-4600-00",
                    "0039-27-4601-00",
                ],
                "nom_historique": [
                    "Maisons-magasins Jacob-De Witt I",
                    "Édifice Aldred",
                    "Hôtel de ville de Montréal",
                ],
                "historique_sommaire": [
                    "<i>dry goods</i> store construit en 1846.",
                    "Gratte-ciel  Art déco.",
                    "Siège de l&#39;administration municipale.",
                ],
                "voie": ["McGill", "Place d'Armes", "Notre-Dame"],
                "arrondissement": ["Ville-Marie", "Ville-Marie", "Ville-Marie"],
                "record_hash": ["a" * 64, "b" * 64, "c" * 64],
                "ingested_at": [datetime.now(UTC)] * 3,
                "source_file": ["edifices_patrimoine.csv"] * 3,
                "pipeline_version": ["0.1.0-test"] * 3,
            }
        )

    @pytest.fixture
    def stage01_parquet(self, cfg: Settings, stage01_df: pd.DataFrame) -> pd.DataFrame:
        cfg.stage_01_out.parent.mkdir(parents=True, exist_ok=True)
        stage01_df.to_parquet(cfg.stage_01_out, compression="snappy", index=False)
        return stage01_df

    def test_creates_output_parquet(self, stage01_parquet: pd.DataFrame, cfg: Settings) -> None:
        s02_clean.run(cfg)
        assert cfg.stage_02_out.is_file()

    def test_row_count_preserved(self, stage01_parquet: pd.DataFrame, cfg: Settings) -> None:
        result = s02_clean.run(cfg)
        assert len(result) == len(stage01_parquet)

    def test_html_stripped_from_historique_sommaire(
        self, stage01_parquet: pd.DataFrame, cfg: Settings
    ) -> None:
        result = s02_clean.run(cfg)
        assert result["historique_sommaire"].iloc[0] == "dry goods store construit en 1846."

    def test_html_entity_and_apostrophe_normalized(
        self, stage01_parquet: pd.DataFrame, cfg: Settings
    ) -> None:
        result = s02_clean.run(cfg)
        # &#39; decoded by BS4 → ' then normalized to ' (U+2019) by typography step
        assert result["historique_sommaire"].iloc[2] == "Siège de l’administration municipale."

    def test_double_space_collapsed(self, stage01_parquet: pd.DataFrame, cfg: Settings) -> None:
        result = s02_clean.run(cfg)
        assert "  " not in str(result["historique_sommaire"].iloc[1])

    def test_straight_apostrophe_normalized_in_voie(
        self, stage01_parquet: pd.DataFrame, cfg: Settings
    ) -> None:
        result = s02_clean.run(cfg)
        assert result["voie"].iloc[1] == "Place d’Armes"
