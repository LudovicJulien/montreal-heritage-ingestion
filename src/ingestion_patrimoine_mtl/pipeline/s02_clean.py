from __future__ import annotations

import re
from pathlib import Path

import ftfy
import pandas as pd
from bs4 import BeautifulSoup
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.schemas import CleanSchema


def run(cfg: Settings) -> pd.DataFrame:
    """Read raw Parquet, strip HTML from text columns, validate, and write clean Parquet."""
    df = pd.read_parquet(cfg.stage_01_out)
    logger.info("Stage 02 — cleaning {rows} rows from {path}", rows=len(df), path=cfg.stage_01_out)

    df = df.copy()
    df["historique_sommaire"] = df["historique_sommaire"].apply(_strip_html)
    logger.info("Stripped HTML from historique_sommaire")

    text_cols = df.select_dtypes(include="object").columns.tolist()
    for col in text_cols:
        df[col] = df[col].apply(_fix_encoding)
    logger.info("Fixed encoding artifacts in {n} text columns", n=len(text_cols))

    df = _validate_schema(df)
    _write_parquet(df, cfg.stage_02_out)
    logger.info(
        "Stage 02 complete: {rows} rows written to {path}",
        rows=len(df),
        path=cfg.stage_02_out,
    )
    return df


_INLINE_TAG_RE = re.compile(r"<su[pb][^>]*>(.*?)</su[pb]>", re.IGNORECASE | re.DOTALL)


def _strip_html(text: str | None) -> str | None:
    """Extract plain text from an HTML string using BeautifulSoup.

    <sup> and <sub> are stripped via regex before BeautifulSoup parsing so that
    their content is inlined without a separator (e.g. M<sup>e</sup> → "Me",
    not "M e"). Block-level tags still get the space separator from get_text().
    """
    if text is None:
        return None
    inlined = _INLINE_TAG_RE.sub(r"\1", text)
    plain = BeautifulSoup(inlined, "html.parser").get_text(" ")
    return _collapse_whitespace(plain)


def _fix_encoding(text: str | None) -> str | None:
    """Fix Unicode encoding artifacts using ftfy.

    Uses isinstance rather than an identity check so that pandas null sentinels
    (pd.NA, np.nan) are handled safely alongside plain None.
    """
    if not isinstance(text, str):
        return None
    return str(ftfy.fix_text(text))


def _normalize_french_typography(text: str | None) -> str | None:
    """Normalize straight apostrophes to curly and fix French quotation marks."""
    raise NotImplementedError


def _collapse_whitespace(text: str | None) -> str | None:
    """Collapse multiple spaces and line breaks into a single space."""
    if text is None:
        return None
    return re.sub(r"\s+", " ", text).strip()


def _empty_to_none(df: pd.DataFrame) -> pd.DataFrame:
    """Convert empty strings '' to pd.NA across all text columns."""
    raise NotImplementedError


def _validate_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the DataFrame against CleanSchema; raises SchemaError on any violation."""
    return CleanSchema.validate(df)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write the validated DataFrame to a snappy-compressed Parquet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)
