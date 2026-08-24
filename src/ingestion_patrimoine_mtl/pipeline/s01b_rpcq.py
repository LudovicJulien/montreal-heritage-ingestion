from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.schemas import REGIME_CITE, REGIME_CLASSE

# Administrative region label used by both exports for the Montreal agglomeration.
# It covers the whole island, villes liées included — Baie-D'Urfé and Beaconsfield
# are in the region without being part of the Ville de Montréal.
MONTREAL_REGION = "Montréal"

# The reconciled column set: what every downstream stage may rely on, regardless of
# which export a record came from. Anything outside this list is dropped, including
# the protected-grounds and protection-area geometries the classés export carries.
RPCQ_COLUMNS = [
    "bien_id",
    "nom_bien",
    "url_rpcq",
    "description_bien",
    "synthese_historique",
    "statut_juridique",
    "date_statut_juridique",
    "categorie",
    "autorite_protection",
    "regime_protection",
    "no_region_admin",
    "region_admin",
    "municipalite",
    "adresse",
    "debut_construction",
    "fin_construction",
    "usage_princ",
    "sous_usage",
    "latitude",
    "longitude",
    "url_photo",
]

# First point of a WKT MULTIPOINT, e.g. "MULTIPOINT ((-73.567699 45.514985))".
# The axis order is X then Y: the first capture is the LONGITUDE, the second the
# latitude. Reading them the other way round places every building in Somalia.
_WKT_FIRST_POINT = re.compile(r"\(\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class _ExportLayout:
    """How one Données Québec export differs from the reconciled layout.

    The two resources are published by different teams and agree on almost nothing
    mechanical: the classés export is semicolon-separated with a UTF-8 BOM, the cités
    export is comma-separated without one, and each names the same facts differently.
    """

    separator: str
    encoding: str
    regime: str
    renames: Mapping[str, str]


# Immeubles classés (ip_tp_xsl.csv) — 621 records, updated 2026-05-11.
# Coordinates come only as a WKT multipoint; there are no latitude/longitude columns.
CLASSES_LAYOUT = _ExportLayout(
    separator=";",
    # utf-8-sig strips the BOM, without which the first column reads "﻿nom_bien".
    encoding="utf-8-sig",
    regime=REGIME_CLASSE,
    renames={
        "statut_juridique_princ": "statut_juridique",
        "date_attri_stat_jurid_princ": "date_statut_juridique",
        "no_regn_admin": "no_region_admin",
    },
)

# Immeubles cités (donneesouvertesmccipciv3.csv) — 730 records, updated 2023-06-26.
CITES_LAYOUT = _ExportLayout(
    separator=",",
    encoding="utf-8",
    regime=REGIME_CITE,
    renames={
        "date_attribution_stat_jurid_principal_actuel": "date_statut_juridique",
        "autorite": "autorite_protection",
        "de": "debut_construction",
        "a": "fin_construction",
        "usage": "usage_princ",
    },
)


def run(cfg: Settings) -> pd.DataFrame:
    """Load both RPCQ exports and keep the Montreal region.

    This is stage 01b: a parallel ingest path that never touches the Données Montréal
    corpus. The two sources meet at stage 04, which resolves them against each other.
    """
    _ensure_sources_exist(cfg)

    df = _load_exports(cfg)
    logger.info("Loaded {rows} RPCQ records from both open data exports", rows=len(df))

    loaded_rows = len(df)
    df = _filter_montreal_region(df)
    logger.info(
        "Region filter: {kept} record(s) in the Montreal region, {dropped} dropped",
        kept=len(df),
        dropped=loaded_rows - len(df),
    )
    return df


def _ensure_sources_exist(cfg: Settings) -> None:
    """Fail fast: abort the stage if either RPCQ export is missing."""
    for path in (cfg.rpcq_classes_path, cfg.rpcq_cites_path):
        if not path.is_file():
            raise FileNotFoundError(
                f"RPCQ export not found: '{path.resolve()}'. "
                "Run `make rpcq-download` (or `python scripts/download_rpcq_data.py`) "
                "to fetch both Données Québec exports, or adjust INGESTION_RAW_DATA_DIR "
                "/ INGESTION_RPCQ_SUBDIR in your .env."
            )


def _load_exports(cfg: Settings) -> pd.DataFrame:
    """Read both exports and concatenate them into a single reconciled frame.

    621 classés plus 730 cités give 1351 rows before the region filter. The two
    frames are aligned on RPCQ_COLUMNS first, so the concatenation cannot produce
    the ragged union of two different header rows.
    """
    classes = _prepare_export(cfg.rpcq_classes_path, CLASSES_LAYOUT)
    cites = _prepare_export(cfg.rpcq_cites_path, CITES_LAYOUT)
    logger.debug(
        "RPCQ exports read: {n_classes} classés, {n_cites} cités",
        n_classes=len(classes),
        n_cites=len(cites),
    )
    return pd.concat([classes, cites], ignore_index=True)


def _prepare_export(path: Path, layout: _ExportLayout) -> pd.DataFrame:
    """Read one export and bring it onto the reconciled layout."""
    df = _read_csv(path, layout)
    df = _normalize_column_names(df)
    df = _tag_protection_regime(df, layout.regime)
    df = _extract_coordinates(df)
    return _reconcile_columns(df, layout.renames)


def _read_csv(path: Path, layout: _ExportLayout) -> pd.DataFrame:
    """Read an export as ``dtype=str``, the same raw-fidelity rule as stage 01.

    Typing is deliberately deferred: the cités export writes approximate years as
    free text (``"vers 1840"``), so casting here would silently nullify them.
    """
    return pd.read_csv(path, sep=layout.separator, encoding=layout.encoding, dtype=str)


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip and lowercase column names, the convention every stage assumes.

    The classés export mixes cases within one header row (``Wkt_Multipoint_XY``
    next to ``nom_bien``), so this is not a no-op even though most names are
    already lowercase.
    """
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    return df


def _tag_protection_regime(df: pd.DataFrame, regime: str) -> pd.DataFrame:
    """Record which export a row came from as ``regime_protection``.

    The regime is carried by the file, not by a column: every row of the classés
    export is ``classe`` and every row of the cités export is ``cite``. Losing it in
    the concatenation would make the 4 doubly-protected Montreal biens — present in
    both exports under the same ``bien_id`` — indistinguishable duplicates.
    """
    df = df.copy()
    df["regime_protection"] = regime
    return df


def _extract_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure numeric latitude/longitude exist, deriving them from the WKT when needed.

    This is the one place the two layouts differ by more than a name. The cités
    export publishes ``latitude`` and ``longitude`` columns; the classés export
    publishes only ``wkt_multipoint_xy``. Both end up as float columns here, so the
    concatenation cannot produce a column that is text on one half and numeric on
    the other — the single exception to the ``dtype=str`` rule of this stage, and it
    is what lets the schema bound-check the position at all.

    Where a record carries several points — 4 of the 621 classés do — the first one
    is kept: it is the position the RPCQ itself displays for the bien.

    Beware the axis order. In ``MULTIPOINT ((-73.567699 45.514985))`` the first
    number is the longitude and the second the latitude, matching the source's own
    ``_XY`` suffix and the ``centro_x`` / ``centro_y`` convention of stage 03.
    """
    df = df.copy()
    longitudes = _numeric_column(df, "longitude")
    latitudes = _numeric_column(df, "latitude")

    if "wkt_multipoint_xy" in df.columns:
        points = df["wkt_multipoint_xy"].map(_first_wkt_point)
        wkt_lon = pd.Series([point[0] for point in points], index=df.index, dtype="float64")
        wkt_lat = pd.Series([point[1] for point in points], index=df.index, dtype="float64")

        unparsed = int((df["wkt_multipoint_xy"].notna() & wkt_lon.isna()).sum())
        if unparsed:
            logger.warning("Could not parse {n} WKT multipoint value(s)", n=unparsed)

        # A published coordinate wins over the geometry; the WKT only fills the gaps.
        longitudes = longitudes.fillna(wkt_lon)
        latitudes = latitudes.fillna(wkt_lat)

    df["longitude"] = longitudes
    df["latitude"] = latitudes
    return df


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series[float]:
    """Return one column as float, materialised as all-null when the export lacks it."""
    if column not in df.columns:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _first_wkt_point(value: object) -> tuple[float | None, float | None]:
    """Return the (longitude, latitude) of the first point of a WKT multipoint."""
    if not isinstance(value, str):
        return (None, None)
    match = _WKT_FIRST_POINT.search(value)
    if match is None:
        return (None, None)
    return (float(match.group(1)), float(match.group(2)))


def _reconcile_columns(df: pd.DataFrame, renames: Mapping[str, str]) -> pd.DataFrame:
    """Rename an export's columns onto RPCQ_COLUMNS and drop everything else.

    The two exports name the same facts differently — ``de`` / ``a`` against
    ``debut_construction`` / ``fin_construction``, ``autorite`` against
    ``autorite_protection``, ``usage`` against ``usage_princ``. Reconciling before
    the concatenation is what keeps the merged frame rectangular; concatenating
    first would leave every record half-empty under two parallel sets of names.

    ``reindex`` also materialises the columns an export simply does not have, so
    both frames end up with the exact same layout in the same order.
    """
    df = df.rename(columns=dict(renames))
    return df.reindex(columns=RPCQ_COLUMNS)


def _filter_montreal_region(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the records whose administrative region is Montreal.

    The filter is on ``region_admin``, not on ``municipalite``: the region is the
    whole agglomeration, so filtering on the city name would silently drop the
    villes liées — Baie-D'Urfé, Beaconsfield, Kirkland, Westmount and the rest —
    whose buildings are in the Données Montréal corpus stage 04 joins against.

    131 classés plus 48 cités survive, for 175 distinct biens: 4 are both classé
    and cité and therefore appear once per export.
    """
    kept = df["region_admin"] == MONTREAL_REGION
    return df[kept].reset_index(drop=True)
