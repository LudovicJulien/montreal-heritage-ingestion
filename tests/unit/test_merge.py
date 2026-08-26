"""Unit tests — stage 04 · Merge (RPCQ entity resolution and join)."""

from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s04_merge import (
    CANDIDATE_RADIUS_M,
    METHOD_EXACT_NAME,
    run,
)


def _crosswalk(cfg: Settings) -> pd.DataFrame:
    """Read back the crosswalk a run has just written."""
    return pd.read_parquet(cfg.stage_04_crosswalk)


class TestCandidateMatching:
    def test_exact_name_at_a_few_metres_matches(self, merge_sources: Settings) -> None:
        """The corpus's "Maison Hurtubise" and the RPCQ's "Hurtubise", 2 m apart, are one bien."""
        merged = run(merge_sources)

        matched = merged.set_index("identifiant_batiment").loc["0039-27-4599-00"]
        assert matched["bien_id"] == "92513"
        assert matched["match_method"] == METHOD_EXACT_NAME

    def test_exact_name_two_kilometres_away_does_not_match(self, merge_sources: Settings) -> None:
        """An identical name outside the radius is a different building, not a weak match.

        The corpus and the RPCQ both hold a "Théâtre Outremont", 2 km apart in the
        fixture. Name alone must never carry a pair: Montreal has several buildings
        under the same historical name.
        """
        merged = run(merge_sources)

        unmatched = merged.set_index("identifiant_batiment").loc["0039-27-4601-00"]
        assert pd.isna(unmatched["bien_id"])

    def test_a_building_without_coordinates_never_matches(self, merge_sources: Settings) -> None:
        """59 of the 1335 real records have no position, so they produce no candidate."""
        merged = run(merge_sources)

        located = merged.set_index("identifiant_batiment").loc["0039-27-4603-00"]
        assert pd.isna(located["bien_id"])

    def test_accepted_pairs_are_within_the_candidate_radius(self, merge_sources: Settings) -> None:
        """The crosswalk carries the distance, and every one of them respects the block."""
        run(merge_sources)

        crosswalk = _crosswalk(merge_sources)
        assert (crosswalk["distance_m"] <= CANDIDATE_RADIUS_M).all()

    def test_a_bien_present_in_both_exports_matches_once(self, merge_sources: Settings) -> None:
        """92513 is both classé and cité; collapsed to one bien, it yields one crosswalk row.

        Without the collapse it would present as two candidates a hair apart and
        the ambiguity rule would refuse it — the doubly-protected biens would be
        exactly the ones the merge could never resolve.
        """
        run(merge_sources)

        crosswalk = _crosswalk(merge_sources)
        assert (crosswalk["bien_id"] == "92513").sum() == 1
