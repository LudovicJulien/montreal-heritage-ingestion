from __future__ import annotations

from typing import NamedTuple

# Bbox de l'île de Montréal (WGS84)
MONTREAL_LAT_MIN = 45.3
MONTREAL_LAT_MAX = 45.8
MONTREAL_LON_MIN = -74.1
MONTREAL_LON_MAX = -73.4

# Les 19 arrondissements officiels de la Ville de Montréal
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


class WGS84Coords(NamedTuple):
    latitude: float
    longitude: float


def is_in_montreal_bbox(lat: float, lon: float) -> bool:
    """Vérifie que des coordonnées WGS84 tombent dans la bbox de Montréal."""
    return (
        MONTREAL_LAT_MIN <= lat <= MONTREAL_LAT_MAX and MONTREAL_LON_MIN <= lon <= MONTREAL_LON_MAX
    )


def is_valid_arrondissement(name: str) -> bool:
    """Vérifie que le nom d'arrondissement appartient à la liste officielle des 19."""
    return name in MONTREAL_ARRONDISSEMENTS


def lambert_to_wgs84(x: float, y: float) -> WGS84Coords:
    """Convertit des coordonnées Lambert NAD83 Québec (EPSG:32198) en WGS84.

    À implémenter si CENTRO_X/Y s'avère être en Lambert NAD83 dans le CSV source.
    Utiliser pyproj : Transformer.from_crs("EPSG:32198", "EPSG:4326").
    """
    raise NotImplementedError("Vérifier le CRS de CENTRO_X/Y avant d'implémenter")
