from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.models import BuildingEntities
from ingestion_patrimoine_mtl.utils.taxonomy import TYPOLOGIE_MAPPING, normalize_typologie


def run(cfg: Settings) -> None:
    """Extract NER entities and export to JSONL.

    This is stage 05. It used to be stage 04, before the RPCQ became a second
    source: enriching a corpus that has not been reconciled with the RPCQ yet
    means running the NER twice, since stage 04 fills the missing historical
    prose the NER reads.
    """
    raise NotImplementedError


def _normalize_typologie(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``typologie_normalisee`` from ``typologie_specifique`` (controlled vocabulary).

    ``typologie_specifique`` is left untouched as the source value; the mapped
    value lives in its own column so a reviewer can always trace a facet back to
    what the corpus actually said.

    A raw value ``TYPOLOGIE_MAPPING`` has never seen is logged once at WARNING,
    not once per row — the mapping was built from one extract, and a refresh
    introducing a new category should be loud, never a silently empty facet.
    """
    df = df.copy()
    unmapped = sorted(
        {
            value
            for value in df["typologie_specifique"].dropna().unique()
            if value.casefold() not in TYPOLOGIE_MAPPING
        }
    )
    for value in unmapped:
        logger.warning(
            "typologie_specifique value absent from TYPOLOGIE_MAPPING, passed through "
            "unmapped: {value!r}",
            value=value,
        )
    df["typologie_normalisee"] = df["typologie_specifique"].apply(normalize_typologie)
    return df


def _extract_entities(texts: list[str | None]) -> list[BuildingEntities]:
    """Batch NER with spaCy fr_core_news_lg via nlp.pipe() for throughput."""
    raise NotImplementedError


def _build_enriched_record(
    row: pd.Series[Any],
    entities: BuildingEntities,
) -> dict[str, Any]:
    """Assemble the final BuildingEnriched object with all RAG-ready fields."""
    raise NotImplementedError


def _write_jsonl(records: list[dict[str, Any]], path: str) -> None:
    """Write records to JSONL (one JSON object per line)."""
    raise NotImplementedError
