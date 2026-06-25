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
def sample_raw_df() -> pd.DataFrame:
    """Minimal DataFrame simulating 3 raw records (stage 01)."""
    return pd.DataFrame(
        {
            "no_batiment": ["0039-27-4599-00", "0039-27-4600-00", "0039-27-4601-00"],
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
