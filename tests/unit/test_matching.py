"""Unit tests — entity resolution utilities (utils/matching.py)."""

from __future__ import annotations

from ingestion_patrimoine_mtl.utils.matching import normalize_name


class TestNormalizeName:
    def test_accents_are_stripped(self) -> None:
        """Accented and unaccented spellings must compare equal — the sources differ on them."""
        assert normalize_name("Théâtre Outremont") == "theatre outremont"

    def test_case_is_folded(self) -> None:
        """The corpus writes "Maison isolée", the RPCQ "maison-magasin"; case carries no signal."""
        assert normalize_name("HÔTEL DE VILLE") == normalize_name("Hôtel de Ville")

    def test_generic_leading_noun_is_dropped(self) -> None:
        """The corpus writes "Maison Hurtubise" where the RPCQ writes "Hurtubise"."""
        assert normalize_name("Maison Hurtubise") == "hurtubise"

    def test_several_leading_generic_nouns_are_dropped(self) -> None:
        """The run is stripped, not just the first word: "Ancien édifice de la ..."."""
        assert normalize_name("Ancien édifice de la Banque") == "banque"

    def test_generic_noun_inside_the_name_is_kept(self) -> None:
        """An inner generic noun stays: "Église de l'Hôpital général" is not "Hôpital général"."""
        assert normalize_name("Église de l'Hôpital général") == "eglise de l hopital general"

    def test_hyphens_and_apostrophes_become_spaces(self) -> None:
        """The two sources hyphenate differently, and stage 02 introduces curly apostrophes."""
        assert normalize_name("Jacob-De Witt") == normalize_name("Jacob De Witt")

    def test_curly_and_straight_apostrophes_agree(self) -> None:
        """Stage 02's typographic apostrophe must not split a pair the RPCQ writes straight."""
        assert normalize_name("L’Île-Bizard") == normalize_name("L'Île-Bizard")

    def test_none_input_returns_none(self) -> None:
        """A missing name is not an empty name — 30 records have no nom_historique."""
        assert normalize_name(None) is None

    def test_name_made_only_of_generic_nouns_returns_none(self) -> None:
        """A name like "La Maison" normalizes away entirely; nothing should be matched on it."""
        assert normalize_name("La Maison") is None
