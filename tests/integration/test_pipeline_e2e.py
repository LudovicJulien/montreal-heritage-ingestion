"""Integration test — full pipeline (01→02→03→04→06) on a 10-record sample."""

from __future__ import annotations

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline import (
    s01_ingest,
    s01b_rpcq,
    s02_clean,
    s03_normalize,
    s04_merge,
    s06_export,
)

# Nine real records straight from rawData/edifices_patrimoine.csv (not read at
# runtime — the file is gitignored, fetched by `make download`, and absent in
# CI). Chosen for the edge cases they already carry without any editing: an
# HTML tag in historique_sommaire (row 0), an em-dash arrondissement with a
# leading-space latitude (row 6), the "non applicable" typology sentinel
# (rows 2, 4, 5), a null typologie_specifique (row 8), the 0-year sentinel on
# fin_des_travaux (rows 7, 8), an est_ouest cardinal (row 7), and curly
# apostrophes for the typography normalization (row 4).
_REAL_ROWS: list[dict[str, str | None]] = [
    {
        "IDENTIFIANT_BATIMENT": "0039-27-4599-00",
        "NOM_HISTORIQUE ": "Maisons-magasins Jacob-De Witt  I",
        "TYPOLOGIE_SPECIFIQUE": "maison-magasin",
        "CIVIQUE_MIN": "412",
        "CIVIQUE": "412-414",
        "TYPE_DE_VOIE": "rue",
        "CIVIQUE_MAX": "414",
        "LIEN": None,
        "VOIE": "McGill",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": (
            "Jacob De Witt fait construire un ensemble de maisons-magasins en 1846. Les locataires "
            "sont loués à des marchands de <i>dry goods</i> (tissus, articles de mercerie).\n\n"
            "En 1900, les héritiers Evans se partagent la propriété.\n"
        ),
        "DEBUT_DES_TRAVAUX": "1846",
        "FIN_DES_TRAVAUX": None,
        "CENTRO_X": "-73.5579",
        "CENTRO_Y": "45.5001",
    },
    {
        "IDENTIFIANT_BATIMENT": "0039-27-5992-00",
        "NOM_HISTORIQUE ": "Magasin-entrepôt Dominion Block II",
        "TYPOLOGIE_SPECIFIQUE": "magasin-entrepôt",
        "CIVIQUE_MIN": "404",
        "CIVIQUE": "404",
        "TYPE_DE_VOIE": "rue",
        "CIVIQUE_MAX": "404",
        "LIEN": None,
        "VOIE": "McGill",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": "1866",
        "FIN_DES_TRAVAUX": "1867",
        "CENTRO_X": "-73.5577",
        "CENTRO_Y": "45.5",
    },
    {
        "IDENTIFIANT_BATIMENT": "0039-19-1578-01",
        "NOM_HISTORIQUE ": "394-402 rue Saint-Jacques ",
        "TYPOLOGIE_SPECIFIQUE": "non applicable",
        "CIVIQUE_MIN": "394",
        "CIVIQUE": "394-402",
        "TYPE_DE_VOIE": "rue",
        "CIVIQUE_MAX": "402",
        "LIEN": None,
        "VOIE": "Saint-Jacques",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": "1939",
        "FIN_DES_TRAVAUX": None,
        "CENTRO_X": "-73.5597",
        "CENTRO_Y": "45.5018",
    },
    {
        "IDENTIFIANT_BATIMENT": "0040-20-9193-00",
        "NOM_HISTORIQUE ": "Édifice Lewis",
        "TYPOLOGIE_SPECIFIQUE": "gratte-ciel",
        "CIVIQUE_MIN": "459",
        "CIVIQUE": "459-465",
        "TYPE_DE_VOIE": "rue",
        "CIVIQUE_MAX": "465",
        "LIEN": None,
        "VOIE": "Saint-Jean",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": (
            "En 1913, un nouvel immeuble de bureaux accueille ses premiers occupants. L'architecte "
            "Kenneth Guscotte Rea est le concepteur de cet imposant immeuble de 10 étages.\n\n"
            "En 1970, de nombreuses compagnies d'assurances ont quitté l'immeuble.\n"
        ),
        "DEBUT_DES_TRAVAUX": "1912",
        "FIN_DES_TRAVAUX": "1913",
        "CENTRO_X": "-73.5573",
        "CENTRO_Y": "45.5027",
    },
    {
        "IDENTIFIANT_BATIMENT": "0040-51-0415-00",
        "NOM_HISTORIQUE ": "Immeuble du Montreal Sailors' Institute",
        "TYPOLOGIE_SPECIFIQUE": "non applicable",
        "CIVIQUE_MIN": "165",
        "CIVIQUE": "165-169",
        "TYPE_DE_VOIE": "place",
        "CIVIQUE_MAX": "169",
        "LIEN": None,
        "VOIE": "D'Youville",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": (
            "En 1875, le Montreal Sailors’ Institute(MSI) s’installe sur cet emplacement. En 1987, "
            "les Œuvres de la maison du Père acquierent le bâtiment.\n"
        ),
        "DEBUT_DES_TRAVAUX": "1953",
        "FIN_DES_TRAVAUX": "1954",
        "CENTRO_X": "-73.5546",
        "CENTRO_Y": "45.5029",
    },
    {
        "IDENTIFIANT_BATIMENT": "0040-85-7973-03",
        "NOM_HISTORIQUE ": "Tour marine",
        "TYPOLOGIE_SPECIFIQUE": "non applicable",
        "CIVIQUE_MIN": "1",
        "CIVIQUE": None,
        "TYPE_DE_VOIE": "quai",
        "CIVIQUE_MAX": "1",
        "LIEN": "des",
        "VOIE": "Convoyeurs",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": "1956",
        "FIN_DES_TRAVAUX": "1957",
        "CENTRO_X": "-73.5514",
        "CENTRO_Y": "45.5036",
    },
    {
        "IDENTIFIANT_BATIMENT": "9537-92-4250-01",
        "NOM_HISTORIQUE ": "5225 chemin Côte-Saint-Antoine ",
        "TYPOLOGIE_SPECIFIQUE": "Maison isolée",
        "CIVIQUE_MIN": "5225",
        "CIVIQUE": "5225",
        "TYPE_DE_VOIE": "chemin",
        "CIVIQUE_MAX": "5225",
        "LIEN": "de la",
        "VOIE": "Côte-Saint-Antoine",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Côte-des-Neiges—Notre-Dame-de-Grâce (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": None,
        "FIN_DES_TRAVAUX": None,
        "CENTRO_X": "-73.612854",
        "CENTRO_Y": " 45.477087",
    },
    {
        "IDENTIFIANT_BATIMENT": "9838-27-7383-01",
        "NOM_HISTORIQUE ": "Théâtre Séville",
        "TYPOLOGIE_SPECIFIQUE": "Théâtre / auditorium / cinéma",
        "CIVIQUE_MIN": "2153",
        "CIVIQUE": "2153-2159",
        "TYPE_DE_VOIE": "rue",
        "CIVIQUE_MAX": "2159",
        "LIEN": None,
        "VOIE": "Sainte-Catherine",
        "EST_OUEST": "Ouest",
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": "1928",
        "FIN_DES_TRAVAUX": "0",
        "CENTRO_X": "-73.583134",
        "CENTRO_Y": "45.490947",
    },
    {
        "IDENTIFIANT_BATIMENT": "9999-24-0006-01",
        "NOM_HISTORIQUE ": "Écurie et remise, parc du Mont-Royal",
        "TYPOLOGIE_SPECIFIQUE": None,
        "CIVIQUE_MIN": "4040",
        "CIVIQUE": "4040",
        "TYPE_DE_VOIE": "avenue",
        "CIVIQUE_MAX": "4040",
        "LIEN": "du",
        "VOIE": "Parc",
        "EST_OUEST": None,
        "ARRONDISSEMENT": "Ville-Marie (Montréal)",
        "HISTORIQUE_SOMMAIRE ": None,
        "DEBUT_DES_TRAVAUX": "1930",
        "FIN_DES_TRAVAUX": "0",
        "CENTRO_X": "-73.584013",
        "CENTRO_Y": " 45.511818",
    },
]

# A 10th, synthetic record: the real rejected-row case CLAUDE.md documents —
# nom_historique "Maison Joseph-David", voie "Gouin", arrondissement
# "Ahuntsic-Cartierville (Montréal)", no identifiant_batiment. Stage 03 rejects
# it (ADR-004's one rejection), so the sample proves the full pipeline carries
# that invariant end to end, not just at the stage-03 unit level.
_REJECTED_ROW: dict[str, str | None] = {
    "IDENTIFIANT_BATIMENT": None,
    "NOM_HISTORIQUE ": "Maison Joseph-David",
    "TYPOLOGIE_SPECIFIQUE": None,
    "CIVIQUE_MIN": None,
    "CIVIQUE": None,
    "TYPE_DE_VOIE": None,
    "CIVIQUE_MAX": None,
    "LIEN": None,
    "VOIE": "Gouin",
    "EST_OUEST": None,
    "ARRONDISSEMENT": "Ahuntsic-Cartierville (Montréal)",
    "HISTORIQUE_SOMMAIRE ": None,
    "DEBUT_DES_TRAVAUX": None,
    "FIN_DES_TRAVAUX": None,
    "CENTRO_X": None,
    "CENTRO_Y": None,
}


@pytest.fixture
def pipeline_source(rpcq_exports: Settings) -> Settings:
    """Write the 10-record source CSV; rpcq_exports already wrote the RPCQ inputs.

    Neither RPCQ fixture names a building this sample includes, and the closest
    one — "Maisons-magasins Jacob-De Witt I" at 93 m — sits outside stage 04's
    150 m candidate radius, so the merge always resolves to zero matches here,
    deterministically.
    """
    cfg = rpcq_exports
    df = pd.DataFrame([*_REAL_ROWS, _REJECTED_ROW])
    cfg.source_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.source_path, index=False, encoding="utf-8")
    return cfg


def _run_full_pipeline(cfg: Settings) -> None:
    """Run every implemented stage in order — 05 is excluded, its run() is a stub."""
    s01_ingest.run(cfg)
    s01b_rpcq.run(cfg)
    s02_clean.run(cfg)
    s03_normalize.run(cfg)
    s04_merge.run(cfg)
    s06_export.run(cfg)


class TestPipelineE2E:
    def test_full_pipeline_produces_export_artifacts(self, pipeline_source: Settings) -> None:
        """01→02→03→04→06 runs end to end and writes the three front-end artifacts."""
        _run_full_pipeline(pipeline_source)

        for filename in ("buildings.geojson", "buildings.json", "stats.json"):
            assert (pipeline_source.stage_06_out / filename).is_file()

    def test_all_record_hashes_are_unique(self, pipeline_source: Settings) -> None:
        """Every record_hash stage 01 computes is distinct across the ten source rows."""
        raw = s01_ingest.run(pipeline_source)
        assert raw["record_hash"].nunique() == len(raw)

    def test_pipeline_is_idempotent(self, pipeline_source: Settings) -> None:
        """Re-ingesting the same source a second time skips every row already processed."""
        first_run = s01_ingest.run(pipeline_source)
        second_run = s01_ingest.run(pipeline_source)

        assert len(first_run) == len(_REAL_ROWS) + 1
        assert len(second_run) == 0
