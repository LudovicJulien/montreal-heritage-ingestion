from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Charge le CSV source, hash les lignes et écrit buildings_raw.parquet."""
    raise NotImplementedError


def _detect_encoding(path: str) -> str:
    """Détecte l'encodage du fichier source avec chardet."""
    raise NotImplementedError


def _strip_column_spaces(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les espaces parasites dans les noms de colonnes (ex. 'NOM_HISTORIQUE ')."""
    raise NotImplementedError


def _add_metadata(df: pd.DataFrame, cfg: Settings) -> pd.DataFrame:
    """Ajoute record_hash, ingested_at (UTC), source_file, pipeline_version."""
    raise NotImplementedError


def _idempotence_filter(df: pd.DataFrame, previous_out: str) -> pd.DataFrame:
    """Retourne uniquement les lignes dont le hash diffère du run précédent."""
    raise NotImplementedError
