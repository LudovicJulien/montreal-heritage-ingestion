from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings

# The only two cardinal qualifiers the source uses on a street name.
EST_OUEST_CANONICAL = frozenset({"Est", "Ouest"})

# Abbreviations absent from the current extract, kept as a refresh guard.
EST_OUEST_ABBREVIATIONS = {"E": "Est", "O": "Ouest", "W": "Ouest"}


def run(cfg: Settings) -> pd.DataFrame:
    """Validate types, coordinates, and addresses; produce buildings_normalized.parquet."""
    raise NotImplementedError


def _normalize_voie_type(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase TYPE_DE_VOIE so casing variants collapse onto one value.

    The source holds 16 distinct types for 15 distinct lowercase forms: the single
    collision is ``Avenue`` against ``avenue``. Nulls are preserved as nulls.
    """
    df = df.copy()
    df["type_de_voie"] = df["type_de_voie"].str.lower()
    return df


def _normalize_est_ouest(df: pd.DataFrame) -> pd.DataFrame:
    """Map EST_OUEST abbreviations onto their canonical cardinal form.

    The current extract holds only ``Est``, ``Ouest`` and nulls — no abbreviation
    survives in the published data. The mapping is kept as a guard: a future refresh
    reintroducing ``E`` or ``O`` is normalized rather than silently carried through.
    """
    df = df.copy()
    df["est_ouest"] = df["est_ouest"].map(_canonical_est_ouest)
    return df


def _canonical_est_ouest(value: object) -> str | None:
    """Return the canonical cardinal direction for a raw EST_OUEST cell."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in EST_OUEST_CANONICAL:
        return stripped
    return EST_OUEST_ABBREVIATIONS.get(stripped.upper().rstrip("."), stripped)


def _validate_arrondissement(df: pd.DataFrame) -> pd.DataFrame:
    """Reject rows whose ARRONDISSEMENT is not in the official 19-borough list."""
    raise NotImplementedError


def _cast_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Cast CENTRO_X/Y to float and validate against the Montreal WGS84 bounding box."""
    raise NotImplementedError


def _cast_years(df: pd.DataFrame) -> pd.DataFrame:
    """Cast DEBUT_DES_TRAVAUX / FIN_DES_TRAVAUX to nullable int, clamped to [1600, 2030]."""
    raise NotImplementedError
