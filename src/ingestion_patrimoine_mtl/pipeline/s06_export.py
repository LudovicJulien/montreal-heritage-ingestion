from __future__ import annotations

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Shape the merged corpus into the flat record the front-end reads.

    This is stage 06, the last of the pipeline: buildings.geojson, buildings.json
    and stats.json are static files the front-end fetches directly — carte,
    facettes, fiches — with no API and no stage 05 dependency, since typologie is
    the one field stage 05 would have carried and it is already a public,
    testable mapping (utils.taxonomy) rather than something only the unfinished
    NER run() produces.
    """
    df = _load_source(cfg)
    df = _map_coordinates(df)
    return df


def _load_source(cfg: Settings) -> pd.DataFrame:
    """Read the merged corpus — stage 04's output, the last one before export."""
    df = pd.read_parquet(cfg.stage_04_out)
    logger.info(
        "Stage 06 — exporting {rows} merged row(s) from {path}",
        rows=len(df),
        path=cfg.stage_04_out,
    )
    return df


def _map_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Rename centro_x/centro_y to longitude/latitude.

    CENTRO_X is the longitude, CENTRO_Y the latitude. Swapping them puts every
    building in Somalia, and nothing downstream of this stage re-derives the
    invariant the way NormalizedSchema's bbox check does — a front-end map has
    no schema to catch it, so the rename happens exactly once, here.
    """
    df = df.copy()
    df["latitude"] = df["centro_y"]
    df["longitude"] = df["centro_x"]
    return df
