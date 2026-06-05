from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Nettoie le HTML, corrige l'encodage et normalise la typographie française."""
    raise NotImplementedError


def _strip_html(text: str | None) -> str | None:
    """Extrait le texte brut depuis une chaîne HTML avec BeautifulSoup."""
    raise NotImplementedError


def _fix_encoding(text: str | None) -> str | None:
    """Corrige les artefacts d'encodage Unicode avec ftfy."""
    raise NotImplementedError


def _normalize_french_typography(text: str | None) -> str | None:
    """Normalise apostrophes droites → courbes et guillemets français."""
    raise NotImplementedError


def _collapse_whitespace(text: str | None) -> str | None:
    """Réduit les espaces multiples et sauts de ligne en espace simple."""
    raise NotImplementedError


def _empty_to_none(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit les chaînes vides '' en pd.NA sur toutes les colonnes texte."""
    raise NotImplementedError
