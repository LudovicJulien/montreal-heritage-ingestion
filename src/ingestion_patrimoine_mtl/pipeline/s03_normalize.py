from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.schemas import NormalizedSchema
from ingestion_patrimoine_mtl.utils.geo import (
    MONTREAL_AGGLOMERATION,
    MONTREAL_ARRONDISSEMENTS,
    MONTREAL_VILLES_LIEES,
    canonicalize_municipality,
    is_in_montreal_bbox,
)

# Values of the municipalite_type column added by this stage.
MUNICIPALITE_ARRONDISSEMENT = "arrondissement"
MUNICIPALITE_VILLE_LIEE = "ville_liee"

# The only two cardinal qualifiers the source uses on a street name.
EST_OUEST_CANONICAL = frozenset({"Est", "Ouest"})

# Abbreviations absent from the current extract, kept as a refresh guard.
EST_OUEST_ABBREVIATIONS = {"E": "Est", "O": "Ouest", "W": "Ouest"}

# Plausible bounds for a construction year on a Montreal heritage building.
# The observed valid range is 1669-2013; the sentinels 0 and 9999 fall outside.
YEAR_MIN = 1600
YEAR_MAX = 2030

YEAR_COLS = ["debut_des_travaux", "fin_des_travaux"]

# Columns whose null rate is worth tracking across runs.
REPORTED_COLS = [
    "nom_historique",
    "voie",
    "type_de_voie",
    "est_ouest",
    "arrondissement",
    "debut_des_travaux",
    "fin_des_travaux",
    "centro_x",
    "centro_y",
]


def run(cfg: Settings) -> pd.DataFrame:
    """Normalize types, coordinates and addresses, then validate against NormalizedSchema.

    Rejection comes first: dropping the identity-less rows keeps every downstream
    count consistent with what is actually written.
    """
    df = pd.read_parquet(cfg.stage_02_out)
    logger.info(
        "Stage 03 — normalizing {rows} rows from {path}", rows=len(df), path=cfg.stage_02_out
    )

    loaded_rows = len(df)
    df = _reject_missing_identifier(df)
    logger.info(
        "Identity filter: {rejected} row(s) rejected, {kept} kept",
        rejected=loaded_rows - len(df),
        kept=len(df),
    )

    df = _normalize_voie_type(df)
    df = _normalize_est_ouest(df)
    df = _validate_arrondissement(df)
    df = _cast_years(df)
    df = _cast_coordinates(df)

    _log_quality_report(df)

    df = _validate_schema(df)
    _write_parquet(df, cfg.stage_03_out)
    logger.info(
        "Stage 03 complete: {rows} rows written to {path}", rows=len(df), path=cfg.stage_03_out
    )
    return df


def _log_quality_report(df: pd.DataFrame) -> None:
    """Log null rates and municipality tagging for the normalized frame.

    A silent nullification is indistinguishable from source data that was already
    null, which makes a quality regression after a data refresh invisible. These
    counts are the audit trail (ADR-004).
    """
    total = len(df)
    if not total:
        logger.warning("Quality report skipped: no rows to report on")
        return

    for col in REPORTED_COLS:
        nulls = int(df[col].isna().sum())
        logger.info(
            "Null rate {col}: {nulls}/{total} ({pct:.1f}%)",
            col=col,
            nulls=nulls,
            total=total,
            pct=100 * nulls / total,
        )

    tagging = df["municipalite_type"].value_counts(dropna=False).to_dict()
    logger.info("Municipality tagging: {tagging}", tagging=tagging)


def _validate_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the DataFrame against NormalizedSchema; raises SchemaError on violation."""
    return NormalizedSchema.validate(df)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write the validated DataFrame to a snappy-compressed Parquet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


def _reject_missing_identifier(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with no identifiant_batiment — the only rejection ADR-004 allows.

    A record without an identifier cannot be deduplicated, traced back to the
    source, or referenced by a retrieval answer: it has no identity to preserve.
    Every other constraint violation degrades a field to null and keeps the row.

    One row is affected in the current extract.
    """
    missing = df["identifiant_batiment"].isna()
    rejected = int(missing.sum())
    if rejected:
        logger.warning("Rejected {n} row(s) with no identifiant_batiment", n=rejected)
    return df[~missing].reset_index(drop=True)


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
    """Canonicalize ARRONDISSEMENT and log values outside the agglomeration allowlist.

    Matching runs on the canonical form produced by ``canonicalize_municipality``:
    the raw labels match none of the official names, so comparing them directly
    would flag all 1336 records.

    Values are checked against the 19 boroughs plus the 15 villes liées. A ville
    liée is an independent municipality of the agglomeration, not a data error —
    its buildings are valid heritage records, so nothing is rejected here (ADR-004).
    """
    df = df.copy()
    canonical = df["arrondissement"].map(canonicalize_municipality)

    unknown = canonical.notna() & ~canonical.isin(MONTREAL_AGGLOMERATION)
    for value in sorted(df.loc[unknown, "arrondissement"].dropna().unique()):
        logger.warning(
            "Nullified ARRONDISSEMENT outside the agglomeration allowlist: {value!r}", value=value
        )

    # A value matching neither a borough nor a known ville liée is nullified: the
    # record stays in the corpus, it simply loses a municipality it cannot prove.
    df["arrondissement"] = canonical.where(~unknown)
    df["municipalite_type"] = canonical.map(_municipality_type)
    return df


def _municipality_type(name: object) -> str | None:
    """Classify a canonical municipality name as a borough or a ville liée.

    Materializing the distinction as a column rather than a log line keeps the
    scope decision open: whoever consumes the output filters to the Ville de
    Montréal proper with a single predicate, and nothing is destroyed if the
    answer changes (ADR-004).
    """
    if name in MONTREAL_ARRONDISSEMENTS:
        return MUNICIPALITE_ARRONDISSEMENT
    if name in MONTREAL_VILLES_LIEES:
        return MUNICIPALITE_VILLE_LIEE
    return None


def _cast_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Cast CENTRO_X/Y to float and nullify positions outside the Montreal bbox.

    The source is already in WGS84 — no projection is applied. Note the axis order:
    ``centro_x`` is the **longitude** and ``centro_y`` the **latitude**.

    Coordinates are nullified as a pair: half a position cannot place a building.
    No row in the current extract falls outside the box, so this acts as a
    regression guard for future refreshes rather than a filter.
    """
    df = df.copy()
    longitude = pd.to_numeric(df["centro_x"], errors="coerce")
    latitude = pd.to_numeric(df["centro_y"], errors="coerce")

    inside = pd.Series(
        [
            bool(pd.notna(lon) and pd.notna(lat) and is_in_montreal_bbox(lat=lat, lon=lon))
            for lon, lat in zip(longitude, latitude, strict=True)
        ],
        index=df.index,
        dtype=bool,
    )

    outside = (longitude.notna() | latitude.notna()) & ~inside
    if int(outside.sum()):
        logger.warning(
            "Nullified {n} coordinate pair(s) outside the Montreal bbox", n=int(outside.sum())
        )

    df["centro_x"] = longitude.where(inside)
    df["centro_y"] = latitude.where(inside)
    return df


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
