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
