"""Unit tests — stage 03 · Normalize."""

from __future__ import annotations

import pytest


class TestNormalizeVoieType:
    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_rue_becomes_lowercase(self) -> None: ...

    @pytest.mark.skip(reason="implement with s03_normalize")
    def test_avenue_becomes_lowercase(self) -> None: ...


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
