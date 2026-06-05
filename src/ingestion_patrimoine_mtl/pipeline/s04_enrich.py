from __future__ import annotations

import pandas as pd

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.models import BuildingEntities


def run(cfg: Settings) -> None:
    """Extrait les entités NER et exporte en JSONL pour le RAG engine."""
    raise NotImplementedError


def _extract_entities(texts: list[str | None]) -> list[BuildingEntities]:
    """NER batch avec spaCy fr_core_news_lg via nlp.pipe() pour la performance."""
    raise NotImplementedError


def _build_enriched_record(
    row: pd.Series,  # type: ignore[type-arg]
    entities: BuildingEntities,
) -> dict:  # type: ignore[type-arg]
    """Assemble l'objet final BuildingEnriched avec tous les champs pour le RAG engine."""
    raise NotImplementedError


def _write_jsonl(records: list[dict], path: str) -> None:  # type: ignore[type-arg]
    """Écrit les enregistrements en JSONL (un objet JSON par ligne)."""
    raise NotImplementedError
