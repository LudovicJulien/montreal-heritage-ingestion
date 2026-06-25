from __future__ import annotations

from typing import Any

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.models import BuildingEntities


def run(cfg: Settings) -> None:
    """Extract NER entities and export to JSONL for the RAG engine."""
    raise NotImplementedError


def _extract_entities(texts: list[str | None]) -> list[BuildingEntities]:
    """Batch NER with spaCy fr_core_news_lg via nlp.pipe() for throughput."""
    raise NotImplementedError


def _build_enriched_record(
    row: pd.Series,
    entities: BuildingEntities,
) -> dict[str, Any]:
    """Assemble the final BuildingEnriched object with all RAG-ready fields."""
    raise NotImplementedError


def _write_jsonl(records: list[dict[str, Any]], path: str) -> None:
    """Write records to JSONL (one JSON object per line)."""
    raise NotImplementedError
