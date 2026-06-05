from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BuildingRaw(BaseModel):
    """Enregistrement brut issu du CSV source (stage 01 · Ingest)."""

    no_batiment: str
    nom_historique: str
    typologie: Optional[str] = None
    no_civique: Optional[str] = None
    civique_max: Optional[str] = None
    type_de_voie: Optional[str] = None
    voie: str
    est_ouest: Optional[str] = None
    arrondissement: str
    debut_des_travaux: Optional[int] = None
    fin_des_travaux: Optional[int] = None
    historique_sommaire: Optional[str] = None
    lien: Optional[str] = None
    centro_x: Optional[float] = None
    centro_y: Optional[float] = None
    # Métadonnées de traçabilité
    record_hash: str
    ingested_at: datetime
    source_file: str
    pipeline_version: str


class BuildingEntities(BaseModel):
    """Entités nommées extraites par spaCy fr_core_news_lg (stage 04 · Enrich)."""

    persons: list[str] = Field(default_factory=list)
    orgs: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


class BuildingEnriched(BaseModel):
    """Enregistrement final enrichi — format de sortie JSONL pour le RAG engine."""

    id: str
    nom_historique: str
    typologie: Optional[str] = None
    adresse: str
    arrondissement: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    debut_travaux: Optional[int] = None
    fin_travaux: Optional[int] = None
    text: str
    entities: BuildingEntities = Field(default_factory=BuildingEntities)
    record_hash: str
    ingested_at: datetime
    pipeline_version: str
