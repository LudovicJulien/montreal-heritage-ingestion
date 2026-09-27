from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.utils.taxonomy import normalize_typologie

# BuildingPublic's column set, keyed by the merged-corpus column it comes from.
# Order is the order of BuildingPublic itself, so a reviewer can read the two
# side by side.
_PUBLIC_COLUMNS = {
    "identifiant_batiment": "id",
    "nom_historique": "nom_historique",
    "typologie": "typologie",
    "adresse": "adresse",
    "arrondissement": "arrondissement",
    "latitude": "latitude",
    "longitude": "longitude",
    "debut_des_travaux": "debut_travaux",
    "fin_des_travaux": "fin_travaux",
    "historique_sommaire": "historique_sommaire",
    "statut_juridique": "statut_juridique",
    "url_montreal": "url_montreal",
    "url_rpcq": "url_rpcq",
    "url_photo": "url_photo",
}

# The montreal.ca record page for a building, built from its own identifier.
# ADR-006 forbids fetching this page; constructing the URL and pointing the
# front-end reader at it is not a fetch, it is a link — the legitimate way to
# give access to content this pipeline does not copy.
MONTREAL_URL_TEMPLATE = "https://montreal.ca/repertoire-patrimoine-bati/batiments-patrimoniaux/{id}"


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
    df = _add_montreal_url(df)
    df = _build_public_frame(df)
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


def _add_montreal_url(df: pd.DataFrame) -> pd.DataFrame:
    """Build the montreal.ca record URL from identifiant_batiment — a link, never a fetch.

    Always non-null: stage 03 already rejects the one row of the corpus that
    lacks an identifiant_batiment, so every surviving record has one to build
    the URL from.
    """
    df = df.copy()
    df["url_montreal"] = df["identifiant_batiment"].map(
        lambda identifier: MONTREAL_URL_TEMPLATE.format(id=identifier)
    )
    return df


def _build_public_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce the merged corpus to the BuildingPublic column set.

    typologie is added here through normalize_typologie (utils.taxonomy) — the
    same controlled vocabulary feat/05a-taxonomy already applies — rather than
    exposing the raw 42-value typologie_specifique or waiting on stage 05's
    run(), which the NER it was built for still leaves unimplemented.
    url_rpcq and url_photo carry straight through: they are the only outbound
    link and the only visual the corpus has, already null for every building
    the RPCQ exports do not cover (ADR-005).
    """
    df = df.copy()
    df["typologie"] = df["typologie_specifique"].apply(normalize_typologie)
    return df.rename(columns=_PUBLIC_COLUMNS)[list(_PUBLIC_COLUMNS.values())]
