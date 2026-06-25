from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings


def run(cfg: Settings) -> pd.DataFrame:
    """Strip HTML, fix encoding artifacts, and normalize typography."""
    raise NotImplementedError


def _strip_html(text: str | None) -> str | None:
    """Extract plain text from an HTML string using BeautifulSoup."""
    raise NotImplementedError


def _fix_encoding(text: str | None) -> str | None:
    """Fix Unicode encoding artifacts using ftfy."""
    raise NotImplementedError


def _normalize_french_typography(text: str | None) -> str | None:
    """Normalize straight apostrophes to curly and fix French quotation marks."""
    raise NotImplementedError


def _collapse_whitespace(text: str | None) -> str | None:
    """Collapse multiple spaces and line breaks into a single space."""
    raise NotImplementedError


def _empty_to_none(df: pd.DataFrame) -> pd.DataFrame:
    """Convert empty strings '' to pd.NA across all text columns."""
    raise NotImplementedError
