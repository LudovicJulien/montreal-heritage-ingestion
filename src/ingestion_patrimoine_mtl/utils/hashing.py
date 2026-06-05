from __future__ import annotations

import hashlib
import json

import pandas as pd


def compute_row_hash(row: pd.Series) -> str:
    """Calcule un SHA-256 déterministe pour une ligne de DataFrame.

    Basé sur la sérialisation JSON triée par clé, indépendant de l'ordre des colonnes.
    """
    serialized = json.dumps(
        {k: (str(v) if v is not None else None) for k, v in row.items()},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_dataframe_hashes(df: pd.DataFrame) -> pd.Series:
    """Calcule le SHA-256 de chaque ligne d'un DataFrame."""
    return df.apply(compute_row_hash, axis=1)
