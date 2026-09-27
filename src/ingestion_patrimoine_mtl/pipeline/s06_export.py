from __future__ import annotations

from typing import Any

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
    df = _compose_adresse(df)
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


def _compose_adresse(df: pd.DataFrame) -> pd.DataFrame:
    """Add adresse, built from civique_min/civique_max rather than the civique column.

    civique holds the source's own pre-formatted display string ("412-414"), but
    it is less complete than the parsed bounds — 62 records on the merged extract
    carry a civique_min/civique_max with no civique at all — and it sometimes
    disagrees with them outright (a civique of "305-307" against a civique_min of
    301 and civique_max of 305). Rebuilding the range from the bounds is the
    reliable path; trusting the pre-formatted string is not.
    """
    df = df.copy()
    df["adresse"] = df.apply(_build_adresse, axis=1)
    return df


def _build_adresse(row: pd.Series[Any]) -> str | None:
    """Compose one address string, or None when the building has no voie at all.

    37 records on the merged extract have neither a voie nor a civique_min —
    there is nothing to compose, and a partial string built from est_ouest alone
    would mislead more than an absent field does.
    """
    if pd.isna(row["voie"]):
        return None

    parts: list[str] = []
    if pd.notna(row["civique_min"]):
        if row["civique_min"] == row["civique_max"]:
            parts.append(str(row["civique_min"]))
        else:
            parts.append(f"{row['civique_min']}-{row['civique_max']}")

    voie = str(row["voie"])
    if pd.notna(row["type_de_voie"]):
        voie = f"{str(row['type_de_voie']).capitalize()} {voie}"
    parts.append(voie)

    if pd.notna(row["est_ouest"]):
        parts.append(str(row["est_ouest"]))

    return " ".join(parts)
