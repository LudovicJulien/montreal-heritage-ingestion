from __future__ import annotations

# The 42 raw values of typologie_specifique measured on the stage 04 output
# (2026-08-29 extract), keyed casefolded — the source mixes "Maison isolée" and
# "maison-magasin" conventions inconsistently, and a refresh is not guaranteed to
# keep either. "non applicable", "indéterminée" and "indéterminé" carry no
# typology at all — 532 of 1335 records, 39.9 % — so they map to null rather
# than being displayed as if they were a category. "Édifice de culte" (52) and
# "Édifice religieux" (39) are the source's two labels for the same thing — a
# church, a synagogue, a temple — so both collapse onto "édifice religieux".
# Everything else maps to itself, casefolded: the source already uses one label
# per typology.
TYPOLOGIE_MAPPING: dict[str, str | None] = {
    "non applicable": None,
    "magasin-entrepôt": "magasin-entrepôt",
    "indéterminée": None,
    "maison isolée": "maison isolée",
    "indéterminé": None,
    "édifice de culte": "édifice religieux",
    "maison-magasin": "maison-magasin",
    "édifice religieux": "édifice religieux",
    "gratte-ciel": "gratte-ciel",
    "atelier / entrepôt / usine / garage": "atelier / entrepôt / usine / garage",
    "maison en rangée": "maison en rangée",
    "école": "école",
    "collège / université": "collège / université",
    "maison urbaine façon nouvelle-france": "maison urbaine façon nouvelle-france",
    "hôpital ou clinique": "hôpital ou clinique",
    "théâtre / auditorium / cinéma": "théâtre / auditorium / cinéma",
    "maison contiguë": "maison contiguë",
    "caserne de pompiers": "caserne de pompiers",
    "banque": "banque",
    "centre communautaire / sportif": "centre communautaire / sportif",
    "croix de chemin": "croix de chemin",
    "maison semi-détachée": "maison semi-détachée",
    "immeuble de bureaux": "immeuble de bureaux",
    "tour d’habitation": "tour d’habitation",
    "bibliothèque": "bibliothèque",
    "hôtel de ville": "hôtel de ville",
    "halle d’exposition": "halle d’exposition",
    "moulin": "moulin",
    "club privé": "club privé",
    "élément d’aménagement paysager": "élément d’aménagement paysager",
    "construction pour le transport terrestre": "construction pour le transport terrestre",
    "édifice militaire": "édifice militaire",
    "bâtiment agricole": "bâtiment agricole",
    "prison": "prison",
    "immeuble de rapport": "immeuble de rapport",
    "stade": "stade",
    "bureau de poste": "bureau de poste",
    "bâtiment commercial ou de bureaux": "bâtiment commercial ou de bureaux",
    "restaurant": "restaurant",
    "bâtiment commercial et résidentiel": "bâtiment commercial et résidentiel",
    "laboratoire / centre de recherche": "laboratoire / centre de recherche",
    "station-service": "station-service",
}


def normalize_typologie(raw: str | None) -> str | None:
    """Map a raw ``typologie_specifique`` value onto the controlled vocabulary.

    Casefolds before lookup, so ``"École"`` and ``"école"`` resolve to the same
    entry regardless of which convention a given record happens to use. Returns
    ``None`` for a null input. A raw value absent from ``TYPOLOGIE_MAPPING`` is
    returned unchanged rather than dropped — the mapping is built from one
    extract, and a value it has never seen should surface, not disappear.
    """
    if raw is None:
        return None
    return TYPOLOGIE_MAPPING.get(raw.casefold(), raw)
