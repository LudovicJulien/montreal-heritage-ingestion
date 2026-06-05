from __future__ import annotations

import pytest

from ingestion_patrimoine_mtl.utils.geo import (
    MONTREAL_ARRONDISSEMENTS,
    is_in_montreal_bbox,
    is_valid_arrondissement,
)


class TestIsInMontrealBbox:
    def test_ville_marie_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.5019, lon=-73.5548)

    def test_toronto_is_outside(self) -> None:
        assert not is_in_montreal_bbox(lat=43.6532, lon=-79.3832)

    def test_boundary_lat_min_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.3, lon=-73.8)

    def test_boundary_lat_max_is_inside(self) -> None:
        assert is_in_montreal_bbox(lat=45.8, lon=-73.8)


class TestIsValidArrondissement:
    def test_ville_marie_is_valid(self) -> None:
        assert is_valid_arrondissement("Ville-Marie")

    def test_unknown_name_is_invalid(self) -> None:
        assert not is_valid_arrondissement("Quartier-Inconnu")

    def test_all_19_arrondissements_are_valid(self) -> None:
        assert len(MONTREAL_ARRONDISSEMENTS) == 19
        for arr in MONTREAL_ARRONDISSEMENTS:
            assert is_valid_arrondissement(arr)
