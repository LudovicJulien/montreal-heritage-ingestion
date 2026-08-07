from __future__ import annotations

import pytest

from ingestion_patrimoine_mtl.utils.geo import (
    MONTREAL_AGGLOMERATION,
    MONTREAL_ARRONDISSEMENTS,
    MONTREAL_VILLES_LIEES,
    canonicalize_municipality,
    is_in_montreal_bbox,
    is_valid_arrondissement,
    is_ville_liee,
)


class TestCanonicalizeMunicipality:
    def test_montreal_suffix_is_stripped(self) -> None:
        """The source appends ' (Montréal)' to every borough name."""
        assert canonicalize_municipality("Ville-Marie (Montréal)") == "Ville-Marie"

    def test_em_dash_becomes_en_dash(self) -> None:
        """The source uses U+2014 where the official names use U+2013."""
        assert (
            canonicalize_municipality("Rosemont—La Petite-Patrie (Montréal)")
            == "Rosemont–La Petite-Patrie"
        )

    def test_curly_apostrophe_becomes_straight(self) -> None:
        """Stage 02 rewrites U+0027 as U+2019; the official names use U+0027."""
        assert (
            canonicalize_municipality("L’Île-Bizard—Sainte-Geneviève (Montréal)")
            == "L'Île-Bizard–Sainte-Geneviève"
        )

    @pytest.mark.parametrize(
        "raw",
        [
            "Ville-Marie (Montréal)",
            "Rosemont—La Petite-Patrie (Montréal)",
            "L’Île-Bizard—Sainte-Geneviève (Montréal)",
            "Côte-des-Neiges—Notre-Dame-de-Grâce (Montréal)",
            "Mercier—Hochelaga-Maisonneuve (Montréal)",
            "Villeray—Saint-Michel—Parc-Extension (Montréal)",
        ],
    )
    def test_source_labels_resolve_to_official_names(self, raw: str) -> None:
        """Every source spelling variant lands on a name in the official list."""
        assert canonicalize_municipality(raw) in MONTREAL_ARRONDISSEMENTS

    def test_raw_label_does_not_match_without_canonicalization(self) -> None:
        """The reason this function exists: raw labels match nothing."""
        assert "Ville-Marie (Montréal)" not in MONTREAL_ARRONDISSEMENTS

    def test_none_returns_none(self) -> None:
        assert canonicalize_municipality(None) is None

    def test_blank_returns_none(self) -> None:
        """A whitespace-only label carries no municipality."""
        assert canonicalize_municipality("   ") is None


class TestIsInMontrealBbox:
    def test_ville_marie_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.5019, lon=-73.5548)

    def test_toronto_is_outside(self) -> None:
        assert not is_in_montreal_bbox(lat=43.6532, lon=-79.3832)

    def test_boundary_lat_min_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.3, lon=-73.8)

    def test_boundary_lat_max_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.8, lon=-73.8)


class TestVillesLiees:
    def test_westmount_is_a_ville_liee(self) -> None:
        assert is_ville_liee("Westmount")

    def test_dorval_is_a_ville_liee(self) -> None:
        assert is_ville_liee("Dorval")

    def test_borough_is_not_a_ville_liee(self) -> None:
        """The two lists are disjoint: a borough is not an independent city."""
        assert not is_ville_liee("Ville-Marie")

    def test_unknown_municipality_is_not_a_ville_liee(self) -> None:
        """Laval belongs to another agglomeration entirely."""
        assert not is_ville_liee("Laval")

    def test_there_are_15_villes_liees(self) -> None:
        assert len(MONTREAL_VILLES_LIEES) == 15

    def test_agglomeration_is_the_union_of_both_lists(self) -> None:
        """The allowlist NormalizedSchema enforces covers boroughs and villes liées."""
        assert len(MONTREAL_AGGLOMERATION) == 19 + 15
        assert MONTREAL_ARRONDISSEMENTS <= MONTREAL_AGGLOMERATION
        assert MONTREAL_VILLES_LIEES <= MONTREAL_AGGLOMERATION

    def test_the_two_lists_do_not_overlap(self) -> None:
        """A municipality is either a borough or an independent city, never both."""
        assert not (MONTREAL_ARRONDISSEMENTS & MONTREAL_VILLES_LIEES)


class TestIsValidArrondissement:
    def test_ville_marie_is_valid(self) -> None:
        assert is_valid_arrondissement("Ville-Marie")

    def test_unknown_name_is_invalid(self) -> None:
        assert not is_valid_arrondissement("Quartier-Inconnu")

    def test_all_19_arrondissements_are_valid(self) -> None:
        assert len(MONTREAL_ARRONDISSEMENTS) == 19
        for arr in MONTREAL_ARRONDISSEMENTS:
            assert is_valid_arrondissement(arr)
