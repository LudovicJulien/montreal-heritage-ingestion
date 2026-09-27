from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.utils.taxonomy import normalize_typologie

# Filenames of the three artifacts stage 06 writes under cfg.stage_06_out.
BUILDINGS_GEOJSON_FILENAME = "buildings.geojson"
BUILDINGS_JSON_FILENAME = "buildings.json"
STATS_JSON_FILENAME = "stats.json"

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

    _write_json(_build_geojson(df), cfg.stage_06_out / BUILDINGS_GEOJSON_FILENAME)
    _write_json(_records(df), cfg.stage_06_out / BUILDINGS_JSON_FILENAME)
    _write_json(_build_stats(df), cfg.stage_06_out / STATS_JSON_FILENAME)
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


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a frame to plain dicts with JSON-safe nulls.

    pandas' own missing markers — NaN, pd.NA, NaT — are not valid JSON; ``where``
    replaces every one of them with ``None`` before the frame ever reaches
    ``json.dumps``, rather than leaning on a custom encoder to paper over it.
    """
    clean = df.astype(object).where(df.notna(), None)
    return clean.to_dict(orient="records")  # type: ignore[return-value]


def _to_feature(record: dict[str, Any]) -> dict[str, Any]:
    """One GeoJSON Feature for a building with known coordinates."""
    geometry = {"type": "Point", "coordinates": [record["longitude"], record["latitude"]]}
    return {"type": "Feature", "geometry": geometry, "properties": record}


def _build_geojson(df: pd.DataFrame) -> dict[str, Any]:
    """Build buildings.geojson over the records with coordinates only.

    59 of 1335 buildings on the merged extract carry no centro_x/centro_y — the
    map cannot place them, and a null-geometry Feature is valid GeoJSON but
    useless to a map layer, so they are excluded here rather than passed
    through. They stay in buildings.json: the list and detail views do not need
    a position to render.
    """
    located = df[df["latitude"].notna() & df["longitude"].notna()]
    return {"type": "FeatureCollection", "features": [_to_feature(r) for r in _records(located)]}


def _write_json(data: dict[str, Any] | list[Any], path: Path) -> None:
    """Write data as UTF-8 JSON, creating the parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Precompute facet counts so the front-end never recomputes them client-side.

    Only non-null values enter a facet count: a "no data" bucket dressed up as a
    filterable category is exactly the fabrication ADR-004 rules out for a single
    field, applied here to a facet instead.
    """
    return {
        "total_buildings": int(len(df)),
        "buildings_with_coordinates": int(df["latitude"].notna().sum()),
        "by_arrondissement": _value_counts(df["arrondissement"]),
        "by_typologie": _value_counts(df["typologie"]),
        "by_statut_juridique": _value_counts(df["statut_juridique"]),
    }


def _value_counts(series: pd.Series[Any]) -> dict[str, int]:
    """Count non-null values, sorted by count descending, ties broken alphabetically."""
    counts = series.dropna().value_counts()
    ordered = counts.sort_index().sort_values(ascending=False, kind="stable")
    return {str(label): int(count) for label, count in ordered.items()}
