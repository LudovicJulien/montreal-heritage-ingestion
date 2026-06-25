"""Unit tests — Pandera schemas."""

from __future__ import annotations

import pytest


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
