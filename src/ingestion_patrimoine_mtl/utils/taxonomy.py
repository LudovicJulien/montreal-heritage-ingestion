from __future__ import annotations

# The 42 raw values of typologie_specifique measured on the stage 04 output
# (2026-08-29 extract). "non applicable", "indéterminée" and "indéterminé" carry
# no typology at all — 532 of 1335 records, 39.9 % — so they map to null rather
# than being displayed as if they were a category. "Édifice de culte" (52) and
# "Édifice religieux" (39) are the source's two labels for the same thing — a
# church, a synagogue, a temple — so both collapse onto "Édifice religieux".
TYPOLOGIE_MAPPING: dict[str, str | None] = {
    "non applicable": None,
    "magasin-entrepôt": "magasin-entrepôt",
    "indéterminée": None,
    "Maison isolée": "Maison isolée",
    "indéterminé": None,
    "Édifice de culte": "Édifice religieux",
    "maison-magasin": "maison-magasin",
    "Édifice religieux": "Édifice religieux",
    "gratte-ciel": "gratte-ciel",
    "Atelier / entrepôt / usine / garage": "Atelier / entrepôt / usine / garage",
    "Maison en rangée": "Maison en rangée",
    "École": "École",
    "Collège / université": "Collège / université",
    "maison urbaine façon Nouvelle-France": "maison urbaine façon Nouvelle-France",
    "Hôpital ou clinique": "Hôpital ou clinique",
    "Théâtre / auditorium / cinéma": "Théâtre / auditorium / cinéma",
    "Maison contiguë": "Maison contiguë",
    "Caserne de pompiers": "Caserne de pompiers",
    "Banque": "Banque",
    "Centre communautaire / sportif": "Centre communautaire / sportif",
    "Croix de chemin": "Croix de chemin",
    "Maison semi-détachée": "Maison semi-détachée",
    "Immeuble de bureaux": "Immeuble de bureaux",
    "Tour d’habitation": "Tour d’habitation",
    "Bibliothèque": "Bibliothèque",
    "Hôtel de ville": "Hôtel de ville",
    "Halle d’exposition": "Halle d’exposition",
    "Moulin": "Moulin",
    "Club privé": "Club privé",
    "Élément d’aménagement paysager": "Élément d’aménagement paysager",
    "Construction pour le transport terrestre": "Construction pour le transport terrestre",
    "Édifice militaire": "Édifice militaire",
    "Bâtiment agricole": "Bâtiment agricole",
    "Prison": "Prison",
    "Immeuble de rapport": "Immeuble de rapport",
    "Stade": "Stade",
    "Bureau de poste": "Bureau de poste",
    "Bâtiment commercial ou de bureaux": "Bâtiment commercial ou de bureaux",
    "Restaurant": "Restaurant",
    "Bâtiment commercial et résidentiel": "Bâtiment commercial et résidentiel",
    "Laboratoire / centre de recherche": "Laboratoire / centre de recherche",
    "Station-service": "Station-service",
}


def normalize_typologie(raw: str | None) -> str | None:
    """Map a raw ``typologie_specifique`` value onto the controlled vocabulary.

    Returns ``None`` for a null input. A raw value absent from
    ``TYPOLOGIE_MAPPING`` is returned unchanged rather than dropped — the mapping
    is built from one extract, and a value it has never seen should surface, not
    disappear.
    """
    if raw is None:
        return None
    return TYPOLOGIE_MAPPING.get(raw, raw)
