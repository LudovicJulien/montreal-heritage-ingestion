from __future__ import annotations

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings

# The only two cardinal qualifiers the source uses on a street name.
EST_OUEST_CANONICAL = frozenset({"Est", "Ouest"})

# Abbreviations absent from the current extract, kept as a refresh guard.
EST_OUEST_ABBREVIATIONS = {"E": "Est", "O": "Ouest", "W": "Ouest"}

# Plausible bounds for a construction year on a Montreal heritage building.
# The observed valid range is 1669-2013; the sentinels 0 and 9999 fall outside.
YEAR_MIN = 1600
YEAR_MAX = 2030

YEAR_COLS = ["debut_des_travaux", "fin_des_travaux"]


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

    A value matching neither the canonical forms nor a known abbreviation is
    nullified and logged, never raised on: per ADR-004 a constraint violation
    degrades the field, it does not abort the run.
    """
    df = df.copy()
    df["est_ouest"] = df["est_ouest"].map(_canonical_est_ouest)
    return df


def _canonical_est_ouest(value: object) -> str | None:
    """Return the canonical cardinal direction for a raw EST_OUEST cell, or None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in EST_OUEST_CANONICAL:
        return stripped
    mapped = EST_OUEST_ABBREVIATIONS.get(stripped.upper().rstrip("."))
    if mapped is not None:
        return mapped
    logger.warning("Nullified unexpected EST_OUEST value: {value!r}", value=value)
    return None


def _validate_arrondissement(df: pd.DataFrame) -> pd.DataFrame:
    """Reject rows whose ARRONDISSEMENT is not in the official 19-borough list."""
    raise NotImplementedError


def _cast_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Cast CENTRO_X/Y to float and validate against the Montreal WGS84 bounding box."""
    raise NotImplementedError


def _cast_years(df: pd.DataFrame) -> pd.DataFrame:
    """Cast the construction years to nullable Int64 and nullify implausible values.

    The source encodes an unknown year as the sentinel ``0`` or ``9999`` rather than
    leaving the cell empty — 242 records carry ``fin_des_travaux = 0``, 36% of the
    non-null values. Both sentinels fall outside the plausible range, so a single
    bound check covers them and any other out-of-range year.

    Values are nullified, never clamped: mapping 9999 onto 2030 would fabricate a
    construction date no source supports, and it would be indistinguishable from a
    genuine one downstream (ADR-004).
    """
    df = df.copy()
    for col in YEAR_COLS:
        years = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        implausible = years.notna() & ((years < YEAR_MIN) | (years > YEAR_MAX))
        df[col] = years.mask(implausible)
    return df
