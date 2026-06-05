from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Valide les types, coordonnées et adresses ; produit buildings_normalized.parquet."""
    raise NotImplementedError


def _normalize_voie_type(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise TYPE_DE_VOIE en minuscules (Rue → rue, Avenue → avenue)."""
    raise NotImplementedError


def _normalize_est_ouest(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise EST_OUEST : E → Est, O → Ouest."""
    raise NotImplementedError


def _validate_arrondissement(df: pd.DataFrame) -> pd.DataFrame:
    """Vérifie que ARRONDISSEMENT figure dans la liste des 19 arrondissements officiels."""
    raise NotImplementedError


def _cast_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit CENTRO_X/Y en float et valide la bbox de Montréal (WGS84)."""
    raise NotImplementedError


def _cast_years(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit DEBUT_DES_TRAVAUX / FIN_DES_TRAVAUX en int nullable [1600, 2030]."""
    raise NotImplementedError
