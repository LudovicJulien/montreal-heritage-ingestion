"""Unit tests — stage 02 · Clean."""

from __future__ import annotations

import pytest

from ingestion_patrimoine_mtl.pipeline.s02_clean import _fix_encoding, _strip_html


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
        import pandas as pd

        assert _fix_encoding(pd.NA) is None

    def test_fixes_double_mojibake(self) -> None:
        # "é" double-encoded: UTF-8 bytes misread twice → "Ã\x83Â©"
        assert _fix_encoding("Ã\x83Â©difice") == "édifice"


class TestNormalizeFrenchTypography:
    @pytest.mark.skip(reason="implement with s02_clean")
    def test_replaces_straight_apostrophes(self) -> None: ...

    @pytest.mark.skip(reason="implement with s02_clean")
    def test_no_op_on_none(self) -> None: ...
