"""Unit tests — stage 04 · Merge (RPCQ entity resolution and join)."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
import pytest
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s04_merge import (
    CANDIDATE_RADIUS_M,
    MATCH_THRESHOLD,
    METHOD_EXACT_NAME,
    run,
)
from ingestion_patrimoine_mtl.schemas import TEXT_SOURCE_CORPUS, TEXT_SOURCE_RPCQ


def _crosswalk(cfg: Settings) -> pd.DataFrame:
    """Read back the crosswalk a run has just written."""
    return pd.read_parquet(cfg.stage_04_crosswalk)


@pytest.fixture
def captured_warnings() -> Iterator[list[str]]:
    """Collect the WARNING lines a run emits.

    loguru does not go through the stdlib logging module, so caplog sees nothing;
    a sink is the only way to assert on what the stage told the operator.
    """
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(message), level="WARNING")
    try:
        yield messages
    finally:
        logger.remove(sink_id)


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


class TestAmbiguousPairs:
    def test_two_indistinguishable_biens_leave_the_building_unmatched(
        self, merge_sources: Settings
    ) -> None:
        """Two biens named "Charles-Sheppard 1" and "2", metres apart, cannot both be it.

        This is ADR-004 applied to entity resolution: the top candidate is not
        picked just because it happens to sort first. On the real extract this is
        the Charles-Sheppard and Janvier-Arthur-Vaillancourt terraces — four and
        three identical row houses against as many identically-named biens.
        """
        merged = run(merge_sources)

        ambiguous = merged.set_index("identifiant_batiment").loc["0039-27-4602-00"]
        assert pd.isna(ambiguous["bien_id"])
        assert pd.isna(ambiguous["match_score"])

    def test_an_ambiguous_building_is_absent_from_the_crosswalk(
        self, merge_sources: Settings
    ) -> None:
        """Unresolved means unresolved: no row, not a row with a low score."""
        run(merge_sources)

        crosswalk = _crosswalk(merge_sources)
        assert "0039-27-4602-00" not in set(crosswalk["identifiant_batiment"])

    def test_neither_competing_bien_is_claimed_by_the_ambiguous_building(
        self, merge_sources: Settings
    ) -> None:
        """Refusing the pair must not quietly award the bien to someone else either."""
        run(merge_sources)

        crosswalk = _crosswalk(merge_sources)
        assert not set(crosswalk["bien_id"]) & {"92516", "92517"}

    def test_the_ambiguity_is_logged_with_its_candidates(
        self, merge_sources: Settings, captured_warnings: list[str]
    ) -> None:
        """A count would tell an operator nothing; the log names the competing biens.

        This is a review queue, and what makes it reviewable is that the line
        carries the building, every candidate and its score.
        """
        run(merge_sources)

        warnings = [line for line in captured_warnings if "0039-27-4602-00" in line]
        assert len(warnings) == 1
        assert "92516" in warnings[0]
        assert "92517" in warnings[0]

    def test_every_accepted_score_clears_the_threshold(self, merge_sources: Settings) -> None:
        """A pair below the threshold is dropped, never kept behind a confidence flag."""
        run(merge_sources)

        crosswalk = _crosswalk(merge_sources)
        assert (crosswalk["score"] >= MATCH_THRESHOLD).all()


class TestHistoriqueSommaire:
    def test_an_existing_text_is_never_overwritten(self, merge_sources: Settings) -> None:
        """Row 0 has a corpus text and a matched bien with a synthèse; the corpus wins.

        Not because the corpus text is better — the RPCQ synthèses are usually
        longer — but because overwriting is unreviewable. A wrong match at 0.71
        would rewrite the history of a building nobody would think to re-check.
        """
        merged = run(merge_sources)

        kept = merged.set_index("identifiant_batiment").loc["0039-27-4599-00"]
        assert kept["historique_sommaire"] == "Texte historique déjà présent dans le corpus."
        assert kept["historique_source"] == TEXT_SOURCE_CORPUS

    def test_a_null_text_is_filled_from_the_rpcq_synthese(self, merge_sources: Settings) -> None:
        """Row 1 has a matched bien and no text of its own — this is why the merge exists."""
        merged = run(merge_sources)

        filled = merged.set_index("identifiant_batiment").loc["0039-27-4600-00"]
        assert filled["historique_sommaire"] == "Synthèse du RPCQ pour Aldred."
        assert filled["historique_source"] == TEXT_SOURCE_RPCQ

    def test_the_rpcq_synthese_is_kept_alongside_the_corpus_text(
        self, merge_sources: Settings
    ) -> None:
        """Not overwriting is only reversible if the synthèse survives in its own column."""
        merged = run(merge_sources)

        kept = merged.set_index("identifiant_batiment").loc["0039-27-4599-00"]
        assert kept["synthese_historique"] == "Synthèse du RPCQ pour Hurtubise."

    def test_an_unmatched_building_has_no_text_source(self, merge_sources: Settings) -> None:
        """No text means no provenance — an empty string here would be a claim of one."""
        merged = run(merge_sources)

        unmatched = merged.set_index("identifiant_batiment").loc["0039-27-4604-00"]
        assert pd.isna(unmatched["historique_source"])

    def test_an_unmatched_bien_leaks_no_text_into_the_corpus(self, merge_sources: Settings) -> None:
        """92518 has a synthèse and no coordinates; nothing may pick it up."""
        merged = run(merge_sources)

        assert "Synthèse orpheline." not in set(merged["historique_sommaire"].dropna())
