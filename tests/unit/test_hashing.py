from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.utils.hashing import compute_dataframe_hashes, compute_row_hash


class TestComputeRowHash:
    def test_returns_64_char_hex(self) -> None:
        row = pd.Series({"a": "hello", "b": "world"})
        h = compute_row_hash(row)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_is_deterministic(self) -> None:
        row = pd.Series({"a": "hello", "b": "world"})
        assert compute_row_hash(row) == compute_row_hash(row)

    def test_different_values_yield_different_hash(self) -> None:
        assert compute_row_hash(pd.Series({"a": "hello"})) != compute_row_hash(
            pd.Series({"a": "world"})
        )

    def test_column_order_independent(self) -> None:
        row1 = pd.Series({"a": "hello", "b": "world"})
        row2 = pd.Series({"b": "world", "a": "hello"})
        assert compute_row_hash(row1) == compute_row_hash(row2)

    def test_none_values_are_handled(self) -> None:
        row = pd.Series({"a": None, "b": "value"})
        assert len(compute_row_hash(row)) == 64


class TestComputeDataframeHashes:
    def test_returns_series_of_correct_length(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        assert len(compute_dataframe_hashes(df)) == 3

    def test_all_hashes_are_unique(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3]})
        hashes = compute_dataframe_hashes(df)
        assert hashes.nunique() == 3
