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


@pytest.fixture
def sample_rpcq_classes_df() -> pd.DataFrame:
    """Three records in the raw layout of the immeubles classés export (stage 01b).

    Column names are the export's own, before reconciliation: ``statut_juridique_princ``,
    ``no_regn_admin``, ``Wkt_Multipoint_XY``, and no latitude/longitude at all.

    Row 0 is a plain Montreal record. Row 1 is a ville liée whose geometry holds two
    points, and is the same bien as row 2 of the cités fixture. Row 2 is outside the
    Montreal administrative region. ``version`` and ``terrain_protege_situation`` are
    there to be dropped by the reconciliation.
    """
    return pd.DataFrame(
        {
            "nom_bien": [
                "Maisons-magasins Jacob-De Witt I",
                "Maison Hurtubise",
                "Maison Girardin",
            ],
            "bien_id": ["92513", "93001", "92001"],
            "url_rpcq": [
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=92513",
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=93001",
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=92001",
            ],
            "description_bien": ["Édifice commercial.", "Maison rurale.", "Maison urbaine."],
            "synthese_historique": ["Construit en 1846.", "Construite en 1739.", None],
            "statut_juridique_princ": ["Classement", "Classement", "Classement"],
            "date_attri_stat_jurid_princ": ["1974-06-12", "1955-03-01", "1965-09-30"],
            "categorie": ["Immeuble patrimonial"] * 3,
            "autorite_protection": ["Ministre de la Culture et des Communications"] * 3,
            "Wkt_Multipoint_XY": [
                "MULTIPOINT ((-73.554973 45.500323))",
                "MULTIPOINT ((-73.596000 45.487000),(-73.595500 45.486800))",
                "MULTIPOINT ((-71.213000 46.813000))",
            ],
            "no_regn_admin": ["06", "06", "03"],
            "region_admin": ["Montréal", "Montréal", "Capitale-Nationale"],
            "municipalite": ["Montréal", "Westmount", "Québec"],
            "adresse": ["411 rue Saint-Paul Est", "563 chemin de la Côte-Saint-Antoine", "34 rue"],
            "debut_construction": ["1846", "1739", "1690"],
            "fin_construction": ["1847", "1740", "1691"],
            "usage_princ": ["Fonction commerciale", "Fonction résidentielle", "Fonction rés."],
            "sous_usage": [None, None, None],
            "url_photo": ["http://photo/92513.jpg", None, "http://photo/92001.jpg"],
            "terrain_protege_situation": [None, "Terrain protégé", None],
            "version": ["2026-05-11"] * 3,
        }
    )


@pytest.fixture
def sample_rpcq_cites_df() -> pd.DataFrame:
    """Four records in the raw layout of the immeubles cités export (stage 01b).

    The export names the same facts differently: ``statut_juridique``, ``autorite``,
    ``de`` / ``a`` for the construction years, ``usage``, and it publishes real
    latitude/longitude columns instead of a WKT geometry.

    Rows 0 and 1 are villes liées of the agglomeration; row 1 carries no coordinates.
    Row 2 is the bien already present in the classés fixture, under its citation.
    Row 3 is outside the Montreal region.
    """
    return pd.DataFrame(
        {
            "nom_bien": [
                "Hôtel de ville",
                "Maison Fraser",
                "Maison Hurtubise",
                "Maison Lamontagne",
            ],
            "bien_id": ["92989", "93397", "93001", "91000"],
            "url_rpcq": [
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=92989",
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=93397",
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=93001",
                "http://www.patrimoine-culturel.gouv.qc.ca/rpcq/detail.do?id=91000",
            ],
            "description_bien": ["Édifice scolaire.", "Maison de ferme.", "Maison rurale.", None],
            "synthese_historique": ["Bâti en 1817.", None, "Citée en 1990.", "Bâtie en 1744."],
            "statut_juridique": ["Citation"] * 4,
            "date_attribution_stat_jurid_principal_actuel": [
                "1988-04-11",
                "1992-11-02",
                "1990-05-07",
                "1974-01-15",
            ],
            "categorie": ["Immeuble patrimonial"] * 4,
            "autorite": ["Municipalité"] * 4,
            "geometrie": [None, None, None, None],
            "latitude": ["45.412944", None, "45.487000", "48.475000"],
            "longitude": ["-73.937083", None, "-73.596000", "-68.470000"],
            "no_region_admin": ["06", "06", "06", "01"],
            "region_admin": ["Montréal", "Montréal", "Montréal", "Bas-Saint-Laurent"],
            "municipalite": ["Baie-D'Urfé", "Beaconsfield", "Westmount", "Rimouski"],
            "adresse": ["20410 chemin Lakeshore", "1 boulevard Beaconsfield", "563 chemin", "707"],
            "type_periode_premiere_construction": ["Construction"] * 4,
            # The cités export writes approximate years as free text — hence dtype=str.
            "de": ["1817", "vers 1840", "1739", "1744"],
            "a": ["1817", "vers 1840", "1740", "1745"],
            "usage": ["Services et institutions", "Fonction agricole", "Fonction rés.", "Musée"],
            "sous_usage": [None, None, None, None],
            "url_photo": ["http://photo/92989.jpg", None, None, "http://photo/91000.jpg"],
        }
    )


@pytest.fixture
def rpcq_exports(
    cfg: Settings,
    sample_rpcq_classes_df: pd.DataFrame,
    sample_rpcq_cites_df: pd.DataFrame,
) -> Settings:
    """Write both RPCQ fixtures at the configured paths, in their real CSV dialects.

    The classés export is semicolon-separated with a UTF-8 BOM and the cités export
    is comma-separated without one, so the fixture exercises the dialect handling
    rather than assuming a single format.
    """
    cfg.rpcq_source_dir.mkdir(parents=True, exist_ok=True)
    sample_rpcq_classes_df.to_csv(cfg.rpcq_classes_path, sep=";", index=False, encoding="utf-8-sig")
    sample_rpcq_cites_df.to_csv(cfg.rpcq_cites_path, sep=",", index=False, encoding="utf-8")
    return cfg
