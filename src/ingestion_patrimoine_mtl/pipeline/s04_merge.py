from __future__ import annotations

import math

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.utils.matching import haversine_distance_m

# Radius of the candidate search around each building, in metres.
#
# The two sources geocode independently — the corpus publishes a parcel centroid,
# the RPCQ a point placed on the bien — so the same building lands tens of metres
# apart in the two files. 150 m is wide enough to absorb that (the accepted pairs
# sit at a median of a few metres, the widest at 137 m) and narrow enough that a
# Ville-Marie block, where 846 of the 1335 buildings are, yields a handful of
# candidates rather than the whole neighbourhood.
CANDIDATE_RADIUS_M = 150.0

# Metres per degree of latitude, used only to draw the coarse box that avoids
# computing 1276 × 173 haversines. Longitude degrees shrink with the cosine of
# the latitude, which the box accounts for separately.
_METRES_PER_DEGREE_LAT = 111_320.0

# Columns holding one value per protection regime rather than one per bien: a
# bien that is both classé and cité carries two of each. Every other column is
# identical across the two rows.
MULTI_VALUED_COLS = ["statut_juridique", "regime_protection"]

# Separator for the collapsed multi-valued columns: "Citation / Classement".
MULTI_VALUE_SEPARATOR = " / "


def run(cfg: Settings) -> pd.DataFrame:
    """Resolve the corpus against the RPCQ and write the merged frame.

    This is stage 04, where the two ingest paths meet. There is no join key: the
    source CSV holds no RPCQ identifier at all, so the rapprochement is fuzzy —
    normalized name plus geographic proximity — and ADR-004 applies in full. A
    pair that cannot be told apart from its runner-up is logged and left
    unresolved; fabricating a link is worse than not having one.
    """
    buildings, rpcq = _load_sources(cfg)

    candidates = _build_candidate_pairs(buildings, rpcq)
    logger.info(
        "Candidate pairs within {radius:.0f} m: {pairs} over {buildings} building(s)",
        radius=CANDIDATE_RADIUS_M,
        pairs=len(candidates),
        buildings=candidates["identifiant_batiment"].nunique(),
    )

    return buildings


def _load_sources(cfg: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the normalized corpus and the RPCQ reference set, one row per bien."""
    buildings = pd.read_parquet(cfg.stage_03_out)
    logger.info(
        "Stage 04 — merging {rows} normalized rows from {path}",
        rows=len(buildings),
        path=cfg.stage_03_out,
    )

    rpcq = pd.read_parquet(cfg.stage_01b_out)
    rpcq = _deduplicate_biens(rpcq)
    logger.info(
        "RPCQ reference set: {biens} distinct bien(s) from {path}",
        biens=len(rpcq),
        path=cfg.stage_01b_out,
    )
    return buildings, rpcq


def _deduplicate_biens(rpcq: pd.DataFrame) -> pd.DataFrame:
    """Collapse the RPCQ frame to one row per bien_id.

    Stage 01b keeps one row per export, so the 4 Montreal biens that are both
    classé *and* cité appear twice — 179 rows for 175 biens. Matching against the
    raw frame would make every one of them look like two near-identical candidates
    scoring within a hair of each other, which the ambiguity rule would then
    refuse as unresolvable. They are not ambiguous; they are one bien.

    The two rows agree on everything except their protection: the status and the
    regime are joined into "Citation / Classement" rather than arbitrarily picking
    one, since both are true. Every other column takes its first non-null value.
    """
    ordered = rpcq.sort_values(["bien_id", "regime_protection"], kind="stable")

    collapsed = ordered.groupby("bien_id", as_index=False, sort=False).first()
    combined = (
        ordered.groupby("bien_id", sort=False)[MULTI_VALUED_COLS]
        .agg(_join_unique_values)
        .reset_index()
    )
    return collapsed.drop(columns=MULTI_VALUED_COLS).merge(combined, on="bien_id", how="left")


def _join_unique_values(values: pd.Series[str]) -> str | None:
    """Join the distinct non-null values of a group, sorted for determinism."""
    distinct = sorted({str(value) for value in values.dropna()})
    return MULTI_VALUE_SEPARATOR.join(distinct) or None


def _build_candidate_pairs(
    buildings: pd.DataFrame,
    rpcq: pd.DataFrame,
    radius_m: float = CANDIDATE_RADIUS_M,
) -> pd.DataFrame:
    """Pair every geolocated building with the biens within radius_m of it.

    Blocking on distance is what makes the rapprochement tractable and, more
    importantly, what keeps it honest: two buildings can perfectly well share a
    name — Montreal has several "Maison Beaudry" — and the position is the only
    thing that tells them apart.

    A building with no coordinates produces no candidate, and therefore never
    matches. 59 of the 1335 are in that case; they stay in the output with every
    RPCQ column null, exactly like a building the RPCQ does not cover.

    Returns a frame of (identifiant_batiment, bien_id, distance_m), possibly
    empty, with no ordering guarantee.
    """
    located_buildings = buildings[buildings["centro_x"].notna() & buildings["centro_y"].notna()]
    located_biens = rpcq[rpcq["latitude"].notna() & rpcq["longitude"].notna()]
    logger.debug(
        "Geolocated: {buildings}/{total_buildings} building(s), {biens}/{total_biens} bien(s)",
        buildings=len(located_buildings),
        total_buildings=len(buildings),
        biens=len(located_biens),
        total_biens=len(rpcq),
    )

    bien_ids = located_biens["bien_id"].to_numpy()
    bien_lats = located_biens["latitude"].to_numpy(dtype="float64")
    bien_lons = located_biens["longitude"].to_numpy(dtype="float64")

    pairs: list[tuple[str, str, float]] = []
    for identifier, longitude, latitude in zip(
        located_buildings["identifiant_batiment"],
        located_buildings["centro_x"],
        located_buildings["centro_y"],
        strict=True,
    ):
        lat_span, lon_span = _degree_spans(latitude, radius_m)
        # Coarse box first: a full 1276 × 173 haversine sweep computes 220 000
        # distances to keep 2000. The box is a superset of the disc, so it can
        # only over-select — the exact filter below still decides.
        nearby = (abs(bien_lats - latitude) <= lat_span) & (abs(bien_lons - longitude) <= lon_span)

        for bien_id, bien_lat, bien_lon in zip(
            bien_ids[nearby], bien_lats[nearby], bien_lons[nearby], strict=True
        ):
            distance = haversine_distance_m(
                lat1=latitude, lon1=longitude, lat2=bien_lat, lon2=bien_lon
            )
            if distance <= radius_m:
                pairs.append((str(identifier), str(bien_id), distance))

    return pd.DataFrame(pairs, columns=["identifiant_batiment", "bien_id", "distance_m"])


def _degree_spans(latitude: float, radius_m: float) -> tuple[float, float]:
    """Return the (latitude, longitude) half-spans in degrees covering radius_m.

    A degree of longitude shortens with the cosine of the latitude — at Montreal's
    45.5° it is about 30 % shorter than a degree of latitude — so the two spans
    cannot be the same number.
    """
    lat_span = radius_m / _METRES_PER_DEGREE_LAT
    lon_span = lat_span / max(math.cos(math.radians(latitude)), 1e-9)
    return lat_span, lon_span
