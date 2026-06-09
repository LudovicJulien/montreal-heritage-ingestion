"""Tests unitaires — stage 02 · Clean."""

from __future__ import annotations

import pytest


class TestStripHtml:
    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_removes_italic_tags(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_decodes_html_entities(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_returns_none_for_none_input(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_collapses_whitespace_after_strip(self) -> None: ...


class TestNormalizeFrenchTypography:
    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_replaces_straight_apostrophes(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter avec s02_clean")
    def test_no_op_on_none(self) -> None: ...
