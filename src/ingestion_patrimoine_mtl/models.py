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


class RpcqBuilding(BaseModel):
    """Reconciled record from the RPCQ open data exports (stage 01b · Ingest RPCQ).

    Field names are the canonical set produced by ``_reconcile_columns``: the two
    Données Québec exports ship different headers for the same facts (``de`` /
    ``debut_construction``, ``autorite`` / ``autorite_protection``), and this model
    describes the reconciled layout, not either raw header row.

    Only ``bien_id`` is required — it is the RPCQ primary key, present on every
    record of both exports, and the only field stage 04 can key a crosswalk on.
    Everything else is optional: coordinates are absent from 76 cited records, and
    the years are free text (``"vers 1840"``), so they stay strings here exactly as
    stage 01 keeps the source CSV untyped.
    """

    bien_id: str
    nom_bien: str | None = None
    url_rpcq: str | None = None
    description_bien: str | None = None
    synthese_historique: str | None = None
    statut_juridique: str | None = None
    date_statut_juridique: str | None = None
    categorie: str | None = None
    autorite_protection: str | None = None
    regime_protection: str | None = None
    no_region_admin: str | None = None
    region_admin: str | None = None
    municipalite: str | None = None
    adresse: str | None = None
    debut_construction: str | None = None
    fin_construction: str | None = None
    usage_princ: str | None = None
    sous_usage: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    url_photo: str | None = None
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
