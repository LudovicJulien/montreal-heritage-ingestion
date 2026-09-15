"""Unit tests — typology mapping utility (utils/taxonomy.py)."""

from __future__ import annotations

import pytest

from ingestion_patrimoine_mtl.utils.taxonomy import TYPOLOGIE_MAPPING, normalize_typologie

# The 42 raw values of typologie_specifique measured on the stage 04 output
# (2026-08-29 extract), each written exactly as the corpus writes it, against the
# value the mapping must produce. Independent of TYPOLOGIE_MAPPING's own literal
# so a typo in the module does not also appear, unnoticed, in its test.
_RAW_TO_EXPECTED: list[tuple[str, str | None]] = [
    ("non applicable", None),
    ("magasin-entrepôt", "magasin-entrepôt"),
    ("indéterminée", None),
    ("Maison isolée", "maison isolée"),
    ("indéterminé", None),
    ("Édifice de culte", "édifice religieux"),
    ("maison-magasin", "maison-magasin"),
    ("Édifice religieux", "édifice religieux"),
    ("gratte-ciel", "gratte-ciel"),
    ("Atelier / entrepôt / usine / garage", "atelier / entrepôt / usine / garage"),
    ("Maison en rangée", "maison en rangée"),
    ("École", "école"),
    ("Collège / université", "collège / université"),
    ("maison urbaine façon Nouvelle-France", "maison urbaine façon nouvelle-france"),
    ("Hôpital ou clinique", "hôpital ou clinique"),
    ("Théâtre / auditorium / cinéma", "théâtre / auditorium / cinéma"),
    ("Maison contiguë", "maison contiguë"),
    ("Caserne de pompiers", "caserne de pompiers"),
    ("Banque", "banque"),
    ("Centre communautaire / sportif", "centre communautaire / sportif"),
    ("Croix de chemin", "croix de chemin"),
    ("Maison semi-détachée", "maison semi-détachée"),
    ("Immeuble de bureaux", "immeuble de bureaux"),
    ("Tour d’habitation", "tour d’habitation"),
    ("Bibliothèque", "bibliothèque"),
    ("Hôtel de ville", "hôtel de ville"),
    ("Halle d’exposition", "halle d’exposition"),
    ("Moulin", "moulin"),
    ("Club privé", "club privé"),
    ("Élément d’aménagement paysager", "élément d’aménagement paysager"),
    ("Construction pour le transport terrestre", "construction pour le transport terrestre"),
    ("Édifice militaire", "édifice militaire"),
    ("Bâtiment agricole", "bâtiment agricole"),
    ("Prison", "prison"),
    ("Immeuble de rapport", "immeuble de rapport"),
    ("Stade", "stade"),
    ("Bureau de poste", "bureau de poste"),
    ("Bâtiment commercial ou de bureaux", "bâtiment commercial ou de bureaux"),
    ("Restaurant", "restaurant"),
    ("Bâtiment commercial et résidentiel", "bâtiment commercial et résidentiel"),
    ("Laboratoire / centre de recherche", "laboratoire / centre de recherche"),
    ("Station-service", "station-service"),
]


class TestNormalizeTypologie:
    @pytest.mark.parametrize(
        "raw, expected", _RAW_TO_EXPECTED, ids=[r for r, _ in _RAW_TO_EXPECTED]
    )
    def test_every_raw_value_resolves(self, raw: str, expected: str | None) -> None:
        """Each of the 42 raw values measured on the corpus maps to its expected entry."""
        assert normalize_typologie(raw) == expected

    def test_the_expected_table_covers_every_key_of_the_mapping(self) -> None:
        """The 42 cases above are not a sample: they cover TYPOLOGIE_MAPPING exactly."""
        assert {raw.casefold() for raw, _ in _RAW_TO_EXPECTED} == set(TYPOLOGIE_MAPPING)

    def test_duplicate_categories_merge(self) -> None:
        """ "Édifice de culte" and "Édifice religieux" must resolve to the same value."""
        assert normalize_typologie("Édifice de culte") == normalize_typologie("Édifice religieux")

    def test_case_fold_before_lookup(self) -> None:
        """A casing the corpus has never shipped must still resolve, not pass through raw."""
        assert normalize_typologie("ÉCOLE") == normalize_typologie("École") == "école"

    def test_none_input_returns_none(self) -> None:
        """A missing typologie_specifique is not itself a category."""
        assert normalize_typologie(None) is None

    def test_unmapped_value_passes_through_unchanged(self) -> None:
        """A raw value the mapping has never seen surfaces as-is rather than vanishing."""
        assert normalize_typologie("Phare maritime") == "Phare maritime"
