from __future__ import annotations

from typing import NamedTuple

# Montreal Island bounding box (WGS84)
MONTREAL_LAT_MIN = 45.3
MONTREAL_LAT_MAX = 45.8
MONTREAL_LON_MIN = -74.1
MONTREAL_LON_MAX = -73.4

# The 19 official boroughs of the City of Montreal
MONTREAL_ARRONDISSEMENTS: frozenset[str] = frozenset(
    {
        "Ahuntsic-Cartierville",
        "Anjou",
        "Côte-des-Neiges–Notre-Dame-de-Grâce",
        "Lachine",
        "LaSalle",
        "Le Plateau-Mont-Royal",
        "Le Sud-Ouest",
        "L'Île-Bizard–Sainte-Geneviève",
        "Mercier–Hochelaga-Maisonneuve",
        "Montréal-Nord",
        "Outremont",
        "Pierrefonds-Roxboro",
        "Rivière-des-Prairies–Pointe-aux-Trembles",
        "Rosemont–La Petite-Patrie",
        "Saint-Laurent",
        "Saint-Léonard",
        "Verdun",
        "Ville-Marie",
        "Villeray–Saint-Michel–Parc-Extension",
    }
)

# The 15 related municipalities (villes liées) of the Montreal agglomeration.
# These are independent cities, not boroughs of the Ville de Montréal, but the
# heritage dataset covers them: 9 of the 15 hold buildings in the current extract.
MONTREAL_VILLES_LIEES: frozenset[str] = frozenset(
    {
        "Baie-D'Urfé",
        "Beaconsfield",
        "Côte-Saint-Luc",
        "Dollard-Des Ormeaux",
        "Dorval",
        "Hampstead",
        "Kirkland",
        "L'Île-Dorval",
        "Montréal-Est",
        "Montréal-Ouest",
        "Mont-Royal",
        "Pointe-Claire",
        "Sainte-Anne-de-Bellevue",
        "Senneville",
        "Westmount",
    }
)

# Every municipality the dataset may legitimately reference.
MONTREAL_AGGLOMERATION: frozenset[str] = MONTREAL_ARRONDISSEMENTS | MONTREAL_VILLES_LIEES


# The source appends this suffix to every borough name: "Ville-Marie (Montréal)".
_MONTREAL_SUFFIX = " (Montréal)"

# The source separates compound borough names with an em dash, while the official
# names use an en dash.
_EM_DASH = "—"
_EN_DASH = "–"

# Stage 02 rewrites straight apostrophes as typographic ones; the official names
# use the straight form.
_CURLY_APOSTROPHE = "’"
_STRAIGHT_APOSTROPHE = "'"


def canonicalize_municipality(name: str | None) -> str | None:
    """Rewrite a raw municipality label into the canonical form used by the constants.

    Three transformations are needed, and all three are required: without them
    MONTREAL_ARRONDISSEMENTS matches none of the source records.

    - Strip the ``" (Montréal)"`` suffix the source appends to every borough.
    - Map the em dash (U+2014) used by the source onto the en dash (U+2013) of the
      official names.
    - Map the typographic apostrophe (U+2019) back onto the straight apostrophe
      (U+0027). This one is introduced by our own stage 02, in
      ``_normalize_french_typography`` — normalizing here keeps the two stages
      decoupled instead of making the typography stage aware of borough names.

    Returns None for a null or blank input.
    """
    if not isinstance(name, str):
        return None
    canonical = name.removesuffix(_MONTREAL_SUFFIX).strip()
    canonical = canonical.replace(_EM_DASH, _EN_DASH)
    canonical = canonical.replace(_CURLY_APOSTROPHE, _STRAIGHT_APOSTROPHE)
    return canonical or None


class WGS84Coords(NamedTuple):
    latitude: float
    longitude: float


def is_in_montreal_bbox(lat: float, lon: float) -> bool:
    """Return True if the WGS84 coordinates fall within the Montreal bounding box."""
    return (
        MONTREAL_LAT_MIN <= lat <= MONTREAL_LAT_MAX and MONTREAL_LON_MIN <= lon <= MONTREAL_LON_MAX
    )


def is_valid_arrondissement(name: str) -> bool:
    """Return True if the borough name is in the official list of 19 boroughs."""
    return name in MONTREAL_ARRONDISSEMENTS


def is_ville_liee(name: str) -> bool:
    """Return True if the name is one of the 15 villes liées of the agglomeration."""
    return name in MONTREAL_VILLES_LIEES


def lambert_to_wgs84(x: float, y: float) -> WGS84Coords:
    """Convert Lambert NAD83 Quebec (EPSG:32198) coordinates to WGS84.

    Implement if CENTRO_X/Y turns out to be in Lambert NAD83 in the source CSV.
    Use pyproj: Transformer.from_crs("EPSG:32198", "EPSG:4326").
    """
    raise NotImplementedError("Verify the CRS of CENTRO_X/Y before implementing")
