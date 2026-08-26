from __future__ import annotations

import math
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.utils.matching import haversine_distance_m, normalize_name

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

# Weight of the name similarity in the composite score. The name carries the
# identification; the distance only corroborates it. Two buildings 3 m apart is
# the normal state of a Montreal terrace, so proximity alone identifies nothing —
# but a 137 m gap on an exact name is still the same bien geocoded twice.
NAME_WEIGHT = 0.7
DISTANCE_WEIGHT = 1.0 - NAME_WEIGHT

# How the names of an accepted pair matched, recorded in the crosswalk. An exact
# hit on the two normalized names is a far stronger claim than a 0.71 ratio, and
# keeping the distinction lets a reviewer audit the weak half without re-scoring.
METHOD_EXACT_NAME = "exact_name"
METHOD_NAME_DISTANCE = "name_distance"

# Minimum score for a pair to be accepted. Calibrated by reading the ranked pairs
# of the reference extract: above 0.70 the list is clean, and the band just below
# is where "Fonderie Darling" starts meeting "Édifices de la Darling Brothers" —
# related biens, not the same one.
MATCH_THRESHOLD = 0.70

# How far the runner-up must sit below the best candidate for the best to count as
# identified. Within this margin the two are indistinguishable and ADR-004 applies:
# the pair is logged and left unresolved rather than settled on a third decimal.
MATCH_MARGIN = 0.05

# The crosswalk contract: the two identifiers, and enough of the evidence to
# re-judge the pair without re-running the stage.
CROSSWALK_COLUMNS = ["identifiant_batiment", "bien_id", "score", "method", "distance_m"]

# RPCQ fields carried onto a matched building. Deliberately a short list of facts
# the corpus does not already hold: the legal protection, the two links out, and
# the historical prose. Coordinates, address and years are *not* carried — the
# corpus has its own, and importing a second opinion on a value it already states
# would leave two columns disagreeing with no rule for which one wins.
RPCQ_JOINED_COLS = [
    "statut_juridique",
    "regime_protection",
    "url_rpcq",
    "url_photo",
    "synthese_historique",
]

# Columns the merge adds to describe the rapprochement itself, so a consumer can
# tell an RPCQ-backed record from one the corpus stands behind alone.
MATCH_COLS = ["bien_id", "match_score", "match_method"]

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

    scored = _score_candidates(candidates, buildings, rpcq)
    matches, _ambiguous = _select_matches(scored)

    crosswalk = _build_crosswalk(matches)
    _write_parquet(crosswalk, cfg.stage_04_crosswalk)

    merged = _join_rpcq_fields(buildings, crosswalk, rpcq)

    return merged


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


def _score_candidates(
    candidates: pd.DataFrame,
    buildings: pd.DataFrame,
    rpcq: pd.DataFrame,
    radius_m: float = CANDIDATE_RADIUS_M,
) -> pd.DataFrame:
    """Score each candidate pair on normalized name similarity and distance.

    The score is a weighted mean of two components, both in [0, 1]:

    - ``name_similarity`` — the ratio of ``difflib.SequenceMatcher`` over the two
      normalized names. A character-level ratio rather than a token set, because
      the disagreements between the two sources are mostly spelling: "St-James"
      against "Saint-James", "Christ Church" against "Christchurch".
    - ``distance_score`` — the distance rescaled linearly over the search radius,
      1.0 at zero metres and 0.0 at the radius.

    The name is weighted more than twice as heavily as the distance, and that
    asymmetry is the point. Proximity identifies nothing on its own: on a Montreal
    terrace the neighbouring building is 3 m away and scores 0.98 on distance. A
    pair with no name to compare — one side is null, or normalizes away to
    nothing — scores 0 on the name component and cannot clear the threshold on
    distance alone.

    ``method`` records how the name matched, so an accepted pair can be audited
    without re-running the scorer: an exact hit on the normalized names is a much
    stronger claim than a 0.71 ratio, and 101 of the 149 accepted pairs are exact.
    """
    if candidates.empty:
        return candidates.assign(
            name_similarity=pd.Series(dtype="float64"),
            distance_score=pd.Series(dtype="float64"),
            score=pd.Series(dtype="float64"),
            method=pd.Series(dtype="object"),
        )

    building_names = _normalized_names(buildings, "identifiant_batiment", "nom_historique")
    bien_names = _normalized_names(rpcq, "bien_id", "nom_bien")

    scored = candidates.copy()
    left = scored["identifiant_batiment"].map(building_names)
    right = scored["bien_id"].map(bien_names)

    scored["name_similarity"] = [
        _name_similarity(one, other) for one, other in zip(left, right, strict=True)
    ]
    scored["distance_score"] = (1.0 - scored["distance_m"] / radius_m).clip(lower=0.0)
    scored["score"] = (
        NAME_WEIGHT * scored["name_similarity"] + DISTANCE_WEIGHT * scored["distance_score"]
    )
    scored["method"] = [
        METHOD_EXACT_NAME if similarity >= 1.0 else METHOD_NAME_DISTANCE
        for similarity in scored["name_similarity"]
    ]
    return scored


def _normalized_names(df: pd.DataFrame, key_col: str, name_col: str) -> dict[str, str | None]:
    """Map each key to its normalized name, computed once instead of once per pair."""
    return {
        str(key): normalize_name(name) for key, name in zip(df[key_col], df[name_col], strict=True)
    }


def _name_similarity(one: str | None, other: str | None) -> float:
    """Return the SequenceMatcher ratio of two normalized names, 0.0 if either is null.

    A missing name is not a weak signal, it is the absence of one: returning 0.0
    rather than skipping the component keeps such a pair below the threshold
    instead of letting the distance carry it alone.
    """
    if not one or not other:
        return 0.0
    return SequenceMatcher(None, one, other).ratio()


def _select_matches(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the best candidate per building, unless it cannot be told from the next.

    Two rules, in order:

    1. A candidate below MATCH_THRESHOLD is discarded. Not "kept with a low
       confidence flag" — a link nobody would act on is noise in a crosswalk that
       stage 06 turns into a public link out to the RPCQ.
    2. Of the candidates that clear the threshold, the best is accepted only if the
       runner-up sits at least MATCH_MARGIN below it. Otherwise the pair is
       **ambiguous**: both are returned in the second frame, logged at WARNING, and
       the building is left unmatched.

    Rule 2 is ADR-004 applied to entity resolution. The reference extract makes the
    case concretely: "Maisons Charles-Sheppard" is four adjacent, identical row
    houses, and the RPCQ holds "Charles-Sheppard 1" through "4" a couple of metres
    apart. Every pairing scores within 0.006 of every other. Picking the top one
    would fabricate a link indistinguishable from a real one downstream, exactly
    like clamping 9999 to 2030 fabricates a construction date.

    A bien matching several buildings is *not* ambiguous and is left alone: an
    RPCQ bien can legitimately be an ensemble covering a whole terrace. The
    resolution only has to be a function on the building side, where each record
    describes exactly one building.

    Returns (matches, ambiguous) — the first with one row per matched building.
    """
    eligible = scored[scored["score"] >= MATCH_THRESHOLD]
    if eligible.empty:
        return eligible.copy(), eligible.copy()

    ranked = eligible.sort_values(
        ["identifiant_batiment", "score"], ascending=[True, False], kind="stable"
    )
    best = ranked.groupby("identifiant_batiment", sort=False).head(1)
    runner_up = ranked.groupby("identifiant_batiment", sort=False).nth(1)

    contested = runner_up.set_index("identifiant_batiment")["score"]
    gap = best["identifiant_batiment"].map(contested)
    # A building with a single eligible candidate has no runner-up and no gap to
    # measure; NaN must read as "identified", not as "too close to call".
    resolved = gap.isna() | ((best["score"] - gap) >= MATCH_MARGIN)

    matches = best[resolved.to_numpy()]
    ambiguous = ranked[
        ranked["identifiant_batiment"].isin(best.loc[~resolved.to_numpy(), "identifiant_batiment"])
    ]
    _log_ambiguous_pairs(ambiguous)
    return matches.reset_index(drop=True), ambiguous.reset_index(drop=True)


def _log_ambiguous_pairs(ambiguous: pd.DataFrame) -> None:
    """Log every unresolved building and the biens it could not be told apart from.

    Logged one line per building rather than as a count: this is the queue a human
    reviews, and a bare number gives them nothing to review.
    """
    if ambiguous.empty:
        return

    for identifier, group in ambiguous.groupby("identifiant_batiment", sort=True):
        logger.warning(
            "Ambiguous match for {identifier}: {n} candidates within {margin} "
            "({candidates}) — left unresolved (ADR-004)",
            identifier=identifier,
            n=len(group),
            margin=MATCH_MARGIN,
            candidates=", ".join(
                f"{bien_id}={score:.3f}"
                for bien_id, score in zip(group["bien_id"], group["score"], strict=True)
            ),
        )


def _build_crosswalk(matches: pd.DataFrame) -> pd.DataFrame:
    """Reduce the accepted pairs to the crosswalk contract.

    One row per matched building — never per bien, since a bien may cover several
    buildings — carrying the two identifiers plus the evidence: the composite
    score, how the names matched, and the metres between the two geocodings.

    Keeping the evidence is what makes MATCH_THRESHOLD reviewable. Without it,
    raising or lowering the threshold is a blind change; with it, the effect can
    be read straight off the table.
    """
    crosswalk = matches.reindex(columns=CROSSWALK_COLUMNS)
    return crosswalk.sort_values("score", ascending=False, kind="stable").reset_index(drop=True)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a validated DataFrame to a snappy-compressed Parquet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


def _join_rpcq_fields(
    buildings: pd.DataFrame,
    crosswalk: pd.DataFrame,
    rpcq: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join the RPCQ fields of each matched bien onto its building.

    Left, and only left: the corpus is the spine. A building the RPCQ does not
    cover — 1186 of the 1335 — keeps every added column null rather than dropping
    out, and an RPCQ bien that matched nothing simply does not appear. The RPCQ is
    a secondary source (ADR-005); it enriches the corpus, it does not replace it.

    Both joins are one-to-one by construction: the crosswalk holds one row per
    matched building, and ``_deduplicate_biens`` has already collapsed the RPCQ to
    one row per bien_id. The merge validates that rather than trusting it — a
    silent fan-out here would inflate the corpus, which is precisely the failure
    the row-count test guards against.
    """
    match_fields = crosswalk[["identifiant_batiment", "bien_id", "score", "method"]].rename(
        columns={"score": "match_score", "method": "match_method"}
    )

    merged = buildings.merge(
        match_fields,
        on="identifiant_batiment",
        how="left",
        validate="one_to_one",
    )
    return merged.merge(
        rpcq[["bien_id", *RPCQ_JOINED_COLS]],
        on="bien_id",
        how="left",
        validate="many_to_one",
    )
