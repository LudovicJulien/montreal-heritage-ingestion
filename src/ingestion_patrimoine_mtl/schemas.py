from __future__ import annotations

import pandera as pa
from pandera.typing import Series


class RawSchema(pa.DataFrameModel):
    """DataFrame contract — stage 01 · Ingest output (buildings_raw.parquet)."""

    no_batiment: Series[str]
    nom_historique: Series[str]
    voie: Series[str]
    arrondissement: Series[str]
    record_hash: Series[str] = pa.Field(str_length={"min_value": 64, "max_value": 64})
    source_file: Series[str]
    pipeline_version: Series[str]

    class Config:
        strict = False
        coerce = True


class CleanSchema(pa.DataFrameModel):
    """DataFrame contract — stage 02 · Clean output (buildings_clean.parquet)."""

    no_batiment: Series[str]
    nom_historique: Series[str]
    voie: Series[str]
    arrondissement: Series[str]
    record_hash: Series[str]

    class Config:
        strict = False
        coerce = True


class NormalizedSchema(pa.DataFrameModel):
    """DataFrame contract — stage 03 · Normalize output (buildings_normalized.parquet)."""

    no_batiment: Series[str]
    nom_historique: Series[str]
    voie: Series[str]
    arrondissement: Series[str]
    # WGS84 coordinates — Montreal Island bounding box
    # Note: check whether CENTRO_X/Y is Lambert NAD83 (EPSG:32198) in the source CSV
    centro_x: Series[float] = pa.Field(nullable=True, ge=-74.1, le=-73.4)
    centro_y: Series[float] = pa.Field(nullable=True, ge=45.3, le=45.8)
    record_hash: Series[str]

    class Config:
        strict = False
        coerce = True
