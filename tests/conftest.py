from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings


@pytest.fixture
def cfg(tmp_path: Path) -> Settings:
    return Settings(
        raw_data_dir=tmp_path / "rawData",
        data_dir=tmp_path / "data",
        pipeline_version="0.1.0-test",
        log_level="DEBUG",
        log_format="dev",
    )


@pytest.fixture
def sample_clean_df() -> pd.DataFrame:
    """DataFrame simulating stage 02 output, one row per stage 03 edge case.

    Row 0 is clean. Row 1 carries an em dash borough, a cased street type and the
    9999 year sentinel. Row 2 carries the curly apostrophe stage 02 introduces, the
    0 sentinel and coordinates outside the Montreal bbox. Row 3 is a ville liée.
    Row 4 is a municipality outside the agglomeration. Row 5 has no identifier.
    """
    return pd.DataFrame(
        {
            "identifiant_batiment": [
                "0039-27-4599-00",
                "0039-27-4600-00",
                "0039-27-4601-00",
                "0039-27-4602-00",
                "0039-27-4603-00",
                None,
            ],
            "nom_historique": [
                "Maisons-magasins Jacob-De Witt I",
                None,
                "Hôtel de ville",
                "Maison Hurtubise",
                "Ailleurs",
                "Sans identifiant",
            ],
            "type_de_voie": ["rue", "Avenue", None, "chemin", "rue", "rue"],
            "voie": ["McGill", "Laurier", None, "Côte-Saint-Antoine", "Principale", "Sherbrooke"],
            "est_ouest": ["Est", "O", "Nord", None, "Ouest", None],
            "arrondissement": [
                "Ville-Marie (Montréal)",
                "Rosemont—La Petite-Patrie (Montréal)",
                "L’Île-Bizard—Sainte-Geneviève (Montréal)",
                "Westmount",
                "Laval",
                "Ville-Marie (Montréal)",
            ],
            "debut_des_travaux": ["1846", "9999", "0", "1900", "1850", "1875"],
            "fin_des_travaux": ["1847", "1931", None, "2500", "1855", "1880"],
            "centro_x": ["-73.5548", "-73.5560", "-100.0", None, "-73.5500", "-73.5510"],
            "centro_y": ["45.5019", "45.5045", "45.5000", None, "45.5100", "45.5110"],
            "record_hash": [
                "a" * 64,
                "b" * 64,
                "c" * 64,
                "d" * 64,
                "e" * 64,
                "f" * 64,
            ],
        }
    )


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    """Minimal DataFrame simulating 3 raw records (stage 01)."""
    return pd.DataFrame(
        {
            "identifiant_batiment": ["0039-27-4599-00", "0039-27-4600-00", "0039-27-4601-00"],
            "nom_historique": [
                "Maisons-magasins Jacob-De Witt I",
                "Édifice Aldred",
                "Hôtel de ville de Montréal",
            ],
            "historique_sommaire": [
                "<i>dry goods</i> store construit en 1846.",
                "Gratte-ciel Art déco.",
                "Siège de l&#39;administration municipale.",
            ],
            "voie": ["McGill", "Place d'Armes", "Notre-Dame"],
            "type_de_voie": ["rue", "place", "rue"],
            "arrondissement": ["Ville-Marie", "Ville-Marie", "Ville-Marie"],
            "centro_x": [-73.5548, -73.5560, -73.5539],
            "centro_y": [45.5019, 45.5045, 45.5082],
            "debut_des_travaux": [1846, 1929, 1878],
            "fin_des_travaux": [None, 1931, 1882],
        }
    )
