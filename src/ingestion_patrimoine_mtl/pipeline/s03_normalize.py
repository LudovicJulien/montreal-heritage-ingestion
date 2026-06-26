from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Validate types, coordinates, and addresses; produce buildings_normalized.parquet."""
    raise NotImplementedError


def _normalize_voie_type(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize TYPE_DE_VOIE to lowercase (Rue → rue, Avenue → avenue)."""
    raise NotImplementedError


def _normalize_est_ouest(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize EST_OUEST abbreviations: E → Est, O → Ouest."""
    raise NotImplementedError


def _validate_arrondissement(df: pd.DataFrame) -> pd.DataFrame:
    """Reject rows whose ARRONDISSEMENT is not in the official 19-borough list."""
    raise NotImplementedError


def _cast_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Cast CENTRO_X/Y to float and validate against the Montreal WGS84 bounding box."""
    raise NotImplementedError


def _cast_years(df: pd.DataFrame) -> pd.DataFrame:
    """Cast DEBUT_DES_TRAVAUX / FIN_DES_TRAVAUX to nullable int, clamped to [1600, 2030]."""
    raise NotImplementedError
