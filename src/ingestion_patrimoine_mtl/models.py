from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BuildingRaw(BaseModel):
    """Raw record from the source CSV (stage 01 · Ingest).

    Field names mirror the source columns exactly, lowercased by the ingest stage.
    Only ``arrondissement`` is genuinely populated on every record; the identifier,
    the historical name, and the street are all missing on a handful of rows, so
    they are modelled as optional rather than required.
    """

    identifiant_batiment: str | None = None
    nom_historique: str | None = None
    typologie_specifique: str | None = None
    civique_min: str | None = None
    civique: str | None = None
    civique_max: str | None = None
    type_de_voie: str | None = None
    voie: str | None = None
    est_ouest: str | None = None
    arrondissement: str
    debut_des_travaux: int | None = None
    fin_des_travaux: int | None = None
    historique_sommaire: str | None = None
    lien: str | None = None
    centro_x: float | None = None
    centro_y: float | None = None
    # Pipeline traceability metadata
    record_hash: str
    ingested_at: datetime
    source_file: str
    pipeline_version: str


class BuildingEntities(BaseModel):
    """Named entities extracted by spaCy fr_core_news_lg (stage 04 · Enrich)."""

    persons: list[str] = Field(default_factory=list)
    orgs: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


class BuildingEnriched(BaseModel):
    """Final enriched record — JSONL output format for the RAG engine."""

    id: str
    nom_historique: str
    typologie: str | None = None
    adresse: str
    arrondissement: str
    latitude: float | None = None
    longitude: float | None = None
    debut_travaux: int | None = None
    fin_travaux: int | None = None
    text: str
    entities: BuildingEntities = Field(default_factory=BuildingEntities)
    record_hash: str
    ingested_at: datetime
    pipeline_version: str
