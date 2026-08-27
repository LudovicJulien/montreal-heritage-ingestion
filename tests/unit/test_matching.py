"""Unit tests — entity resolution utilities (utils/matching.py)."""

from __future__ import annotations

import pytest

from ingestion_patrimoine_mtl.pipeline.s04_merge import CANDIDATE_RADIUS_M
from ingestion_patrimoine_mtl.utils.matching import haversine_distance_m, normalize_name

# Two points on rue Saint-Jacques, Ville-Marie, a little under the merge's search
# radius apart. The reference is the WGS84 geodesic, computed once with
# geopy.distance.geodesic — the ellipsoidal answer the spherical formula is
# approximating. geopy is not imported here: the point of the test is that the
# approximation holds, not that geopy still returns the same number.
_SAINT_JACQUES_A = (45.5017, -73.5673)
_SAINT_JACQUES_B = (45.5030, -73.5673)
_GEODESIC_DISTANCE_M = 144.484


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


class TestHaversineDistanceM:
    def test_matches_the_geodesic_within_one_metre(self) -> None:
        """At the merge's 150 m scale the spherical formula must agree with the ellipsoid."""
        distance = haversine_distance_m(
            lat1=_SAINT_JACQUES_A[0],
            lon1=_SAINT_JACQUES_A[1],
            lat2=_SAINT_JACQUES_B[0],
            lon2=_SAINT_JACQUES_B[1],
        )
        assert abs(distance - _GEODESIC_DISTANCE_M) < 1.0

    def test_identical_points_are_zero_metres_apart(self) -> None:
        """The two sources sometimes publish the exact same coordinates for a bien."""
        assert haversine_distance_m(45.5017, -73.5673, 45.5017, -73.5673) == 0.0

    def test_distance_is_symmetric(self) -> None:
        """Which frame is queried against which must not move the candidate radius."""
        forward = haversine_distance_m(45.5017, -73.5673, 45.5045, -73.5560)
        backward = haversine_distance_m(45.5045, -73.5560, 45.5017, -73.5673)
        assert forward == pytest.approx(backward)

    def test_swapping_one_sides_axes_is_not_silent(self) -> None:
        """The corpus stores (centro_x, centro_y) and the RPCQ (latitude, longitude).

        The two sources order their axes oppositely, so the realistic mistake is
        reading one side in the other's order — not both, which merely relocates
        the pair while keeping the gap. One swapped side puts the two points
        15 000 km apart, so no candidate is ever built. Worth a test precisely
        because it fails silently: the function still returns a number, the
        candidate frame simply comes back empty.
        """
        correct = haversine_distance_m(45.5017, -73.5673, 45.5030, -73.5673)
        one_side_swapped = haversine_distance_m(45.5017, -73.5673, -73.5673, 45.5030)
        assert correct < CANDIDATE_RADIUS_M
        assert one_side_swapped > 1_000_000
