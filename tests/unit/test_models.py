"""Unit tests — Pydantic domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ingestion_patrimoine_mtl.models import BuildingRaw

# The 16 columns of the source CSV, under the lowercase names ingest produces.
SOURCE_COLUMNS = frozenset(
    {
        "identifiant_batiment",
        "nom_historique",
        "typologie_specifique",
        "civique_min",
        "civique",
        "civique_max",
        "type_de_voie",
        "voie",
        "est_ouest",
        "arrondissement",
        "historique_sommaire",
        "debut_des_travaux",
        "fin_des_travaux",
        "lien",
        "centro_x",
        "centro_y",
    }
)

RECORD_HASH = "a" * 64
INGESTED_AT = datetime(2026, 6, 9, tzinfo=UTC)
SOURCE_FILE = "edifices_patrimoine.csv"
PIPELINE_VERSION = "0.2.0"


class TestBuildingRawFields:
    def test_model_covers_every_source_column(self) -> None:
        """Each of the 16 source columns has a matching field on the model."""
        assert SOURCE_COLUMNS <= set(BuildingRaw.model_fields)

    def test_stale_field_names_are_gone(self) -> None:
        """The pre-sync names no longer exist — they matched no source column."""
        assert "typologie" not in BuildingRaw.model_fields
        assert "no_civique" not in BuildingRaw.model_fields


class TestBuildingRawValidation:
    def test_full_record_is_accepted(self) -> None:
        """A record carrying every source column validates."""
        building = BuildingRaw(
            identifiant_batiment="0039-27-4599-00",
            nom_historique="Maisons-magasins Jacob-De Witt I",
            typologie_specifique="Immeuble commercial",
            civique_min="412",
            civique="412-414",
            civique_max="414",
            type_de_voie="rue",
            voie="McGill",
            est_ouest="Est",
            arrondissement="Ville-Marie",
            historique_sommaire="Construit en 1846.",
            debut_des_travaux=1846,
            fin_des_travaux=1847,
            lien=None,
            centro_x=-73.5548,
            centro_y=45.5019,
            record_hash=RECORD_HASH,
            ingested_at=INGESTED_AT,
            source_file=SOURCE_FILE,
            pipeline_version=PIPELINE_VERSION,
        )
        assert building.typologie_specifique == "Immeuble commercial"
        assert building.civique_min == "412"
        assert building.civique_max == "414"

    def test_optional_source_fields_default_to_none(self) -> None:
        """The identifier, name and street are absent on some real records."""
        building = BuildingRaw(
            arrondissement="Ville-Marie",
            record_hash=RECORD_HASH,
            ingested_at=INGESTED_AT,
            source_file=SOURCE_FILE,
            pipeline_version=PIPELINE_VERSION,
        )
        assert building.identifiant_batiment is None
        assert building.nom_historique is None
        assert building.voie is None

    def test_missing_arrondissement_raises(self) -> None:
        """arrondissement is the only source column populated on every record."""
        with pytest.raises(ValidationError):
            # model_validate rather than the constructor: the missing field is the
            # point of the test, and a direct call would not type-check.
            BuildingRaw.model_validate(
                {
                    "record_hash": RECORD_HASH,
                    "ingested_at": INGESTED_AT,
                    "source_file": SOURCE_FILE,
                    "pipeline_version": PIPELINE_VERSION,
                }
            )
