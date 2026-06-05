from __future__ import annotations

from typing import Optional

import pandera as pa
from pandera.typing import Series


class RawSchema(pa.DataFrameModel):
    """Contrat DataFrame — sortie stage 01 · Ingest (buildings_raw.parquet)."""

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
    """Contrat DataFrame — sortie stage 02 · Clean (buildings_clean.parquet)."""

    no_batiment: Series[str]
    nom_historique: Series[str]
    voie: Series[str]
    arrondissement: Series[str]
    record_hash: Series[str]

    class Config:
        strict = False
        coerce = True


class NormalizedSchema(pa.DataFrameModel):
    """Contrat DataFrame — sortie stage 03 · Normalize (buildings_normalized.parquet)."""

    no_batiment: Series[str]
    nom_historique: Series[str]
    voie: Series[str]
    arrondissement: Series[str]
    # Coordonnées WGS84 — bbox île de Montréal
    # Note: vérifier si CENTRO_X/Y est Lambert NAD83 (EPSG:32198) dans le CSV source
    centro_x: Optional[Series[float]] = pa.Field(nullable=True, ge=-74.1, le=-73.4)
    centro_y: Optional[Series[float]] = pa.Field(nullable=True, ge=45.3, le=45.8)
    record_hash: Series[str]

    class Config:
        strict = False
        coerce = True
