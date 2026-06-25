from __future__ import annotations

import hashlib
import json

import pandas as pd


def compute_row_hash(row: pd.Series) -> str:
    """Compute a deterministic SHA-256 hash for a single DataFrame row.

    Based on key-sorted JSON serialization, independent of column order.
    """
    serialized = json.dumps(
        {k: (str(v) if v is not None else None) for k, v in row.items()},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_dataframe_hashes(df: pd.DataFrame) -> pd.Series:
    """Compute the SHA-256 hash of every row in a DataFrame."""
    return df.apply(compute_row_hash, axis=1)
