from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings


@dataclass(frozen=True)
class _ExportLayout:
    """How one Données Québec export differs from the other.

    The two resources are published by different teams and agree on almost nothing
    mechanical: the classés export is semicolon-separated with a UTF-8 BOM, the cités
    export is comma-separated without one.
    """

    separator: str
    encoding: str


# Immeubles classés (ip_tp_xsl.csv) — 621 records, updated 2026-05-11.
# Coordinates come only as a WKT multipoint; there are no latitude/longitude columns.
CLASSES_LAYOUT = _ExportLayout(
    separator=";",
    # utf-8-sig strips the BOM, without which the first column reads "﻿nom_bien".
    encoding="utf-8-sig",
)

# Immeubles cités (donneesouvertesmccipciv3.csv) — 730 records, updated 2023-06-26.
CITES_LAYOUT = _ExportLayout(
    separator=",",
    encoding="utf-8",
)


def run(cfg: Settings) -> pd.DataFrame:
    """Load both RPCQ exports into a single frame.

    This is stage 01b: a parallel ingest path that never touches the Données Montréal
    corpus. The two sources meet at stage 04, which resolves them against each other.
    """
    _ensure_sources_exist(cfg)

    df = _load_exports(cfg)
    logger.info("Loaded {rows} RPCQ records from both open data exports", rows=len(df))
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
    """Read both exports and concatenate them into a single frame.

    621 classés plus 730 cités give 1351 rows, the whole of what the Données Québec
    open data publishes — the Montreal region filter comes later.
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
    """Read one export with its own CSV dialect."""
    return _read_csv(path, layout)


def _read_csv(path: Path, layout: _ExportLayout) -> pd.DataFrame:
    """Read an export as ``dtype=str``, the same raw-fidelity rule as stage 01.

    Typing is deliberately deferred: the cités export writes approximate years as
    free text (``"vers 1840"``), so casting here would silently nullify them.
    """
    return pd.read_csv(path, sep=layout.separator, encoding=layout.encoding, dtype=str)
