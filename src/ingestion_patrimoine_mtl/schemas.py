from __future__ import annotations

from datetime import datetime

import pandera as pa
from pandera.typing import Series

from ingestion_patrimoine_mtl.utils.geo import (
    MONTREAL_AGGLOMERATION,
    MONTREAL_LAT_MAX,
    MONTREAL_LAT_MIN,
    MONTREAL_LON_MAX,
    MONTREAL_LON_MIN,
)


class RawSchema(pa.DataFrameModel):
    """DataFrame contract — stage 01 · Ingest output (buildings_raw.parquet).

    Source-derived columns are nullable: raw ingestion preserves the CSV as-is
    without rejecting records. Pipeline-generated columns are always non-null.
    """

    identifiant_batiment: Series[str] = pa.Field(nullable=True)
    nom_historique: Series[str] = pa.Field(nullable=True)
    voie: Series[str] = pa.Field(nullable=True)
    arrondissement: Series[str] = pa.Field(nullable=True)
    record_hash: Series[str] = pa.Field(str_length={"min_value": 64, "max_value": 64})
    ingested_at: Series[datetime]
    source_file: Series[str]
    pipeline_version: Series[str]

    class Config:
        strict = False
        coerce = True


# Protection regimes of the RPCQ, one per open data export. Declared here rather
# than in the stage module so the schema can reference them without importing the
# pipeline package back into itself.
REGIME_CLASSE = "classe"
REGIME_CITE = "cite"


class RpcqRawSchema(pa.DataFrameModel):
    """DataFrame contract — stage 01b · Ingest RPCQ output (rpcq_raw.parquet).

    ``bien_id`` is the only non-null column: it is the RPCQ primary key and stage 04
    cannot build a crosswalk row without it. Note that it is **not unique** — 4 of
    the 179 Montreal records are both classés and cités, so they appear once per
    export with a different ``regime_protection``.

    Coordinates are nullable (2 Montreal records carry none) and bounded by the same
    Montreal box as NormalizedSchema, which the whole administrative region fits
    inside. ``statut_juridique`` carries no allowlist: the classés export already
    holds one "Avis d'intention de classement prorogé" alongside "Classement", and a
    refresh may add more.
    """

    bien_id: Series[str]
    url_rpcq: Series[str] = pa.Field(nullable=True)
    nom_bien: Series[str] = pa.Field(nullable=True)
    statut_juridique: Series[str] = pa.Field(nullable=True)
    regime_protection: Series[str] = pa.Field(isin=[REGIME_CLASSE, REGIME_CITE])
    municipalite: Series[str] = pa.Field(nullable=True)
    latitude: Series[float] = pa.Field(nullable=True, ge=MONTREAL_LAT_MIN, le=MONTREAL_LAT_MAX)
    longitude: Series[float] = pa.Field(nullable=True, ge=MONTREAL_LON_MIN, le=MONTREAL_LON_MAX)
    record_hash: Series[str] = pa.Field(str_length={"min_value": 64, "max_value": 64})
    ingested_at: Series[datetime]
    source_file: Series[str]
    pipeline_version: Series[str]

    class Config:
        strict = False
        coerce = True


class CleanSchema(pa.DataFrameModel):
    """DataFrame contract — stage 02 · Clean output (buildings_clean.parquet).

    Source-derived columns remain nullable: the clean stage normalises text but
    does not impute missing values. record_hash is pipeline-generated and must
    always be a valid 64-character SHA-256 hex digest.
    """

    identifiant_batiment: Series[str] = pa.Field(nullable=True)
    nom_historique: Series[str] = pa.Field(nullable=True)
    voie: Series[str] = pa.Field(nullable=True)
    arrondissement: Series[str] = pa.Field(nullable=True)
    record_hash: Series[str] = pa.Field(str_length={"min_value": 64, "max_value": 64})

    class Config:
        strict = False
        coerce = True


class NormalizedSchema(pa.DataFrameModel):
    """DataFrame contract — stage 03 · Normalize output (buildings_normalized.parquet).

    Only ``identifiant_batiment`` is required: stage 03 rejects the rows that lack
    one, so the column is non-null by construction. Every other source column stays
    nullable — the stage degrades a failing field to null rather than dropping the
    record (ADR-004), and ``nom_historique``, ``voie`` and ``arrondissement`` are
    all legitimately absent on some buildings.
    """

    identifiant_batiment: Series[str]
    nom_historique: Series[str] = pa.Field(nullable=True)
    voie: Series[str] = pa.Field(nullable=True)
    arrondissement: Series[str] = pa.Field(nullable=True, isin=MONTREAL_AGGLOMERATION)
    municipalite_type: Series[str] = pa.Field(nullable=True, isin=["arrondissement", "ville_liee"])
    # WGS84 coordinates — Montreal Island bounding box.
    # centro_x is the longitude, centro_y the latitude.
    centro_x: Series[float] = pa.Field(nullable=True, ge=-74.1, le=-73.4)
    centro_y: Series[float] = pa.Field(nullable=True, ge=45.3, le=45.8)
    record_hash: Series[str]

    class Config:
        strict = False
        coerce = True
