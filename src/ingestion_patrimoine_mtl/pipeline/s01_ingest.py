from __future__ import annotations

from pathlib import Path

import chardet
import pandas as pd
from tqdm import tqdm

from ingestion_patrimoine_mtl.config import Settings

# Échantillon suffisant pour une détection fiable sans lire tout le fichier.
_ENCODING_SAMPLE_SIZE = 100_000

# Petit volume (~2 700 lignes) : des chunks de 500 donnent une progression
# visible sans coût de concaténation notable.
_CSV_CHUNK_SIZE = 500


def run(cfg: Settings) -> pd.DataFrame:
    """Charge le CSV source, hash les lignes et écrit buildings_raw.parquet."""
    _ensure_source_exists(cfg)
    encoding = _detect_encoding(cfg.source_path)
    return _load_csv(cfg.source_path, encoding)


def _load_csv(path: Path, encoding: str) -> pd.DataFrame:
    """Charge le CSV par chunks avec barre de progression tqdm.

    Tout est lu en ``dtype=str`` : l'ingestion préserve la fidélité brute
    (zéros de tête des identifiants, années non castées) ; le typage est la
    responsabilité de l'étape normalize.
    """
    chunks: list[pd.DataFrame] = []
    with (
        pd.read_csv(path, encoding=encoding, dtype=str, chunksize=_CSV_CHUNK_SIZE) as reader,
        tqdm(desc=f"Ingestion {path.name}", unit=" lignes") as progress,
    ):
        for chunk in reader:
            chunks.append(chunk)
            progress.update(len(chunk))
    if not chunks:
        # Fichier avec en-tête seul : relire sans chunks pour garder les colonnes.
        return pd.read_csv(path, encoding=encoding, dtype=str)
    return pd.concat(chunks, ignore_index=True)


def _ensure_source_exists(cfg: Settings) -> None:
    """Fail-fast : interrompt le pipeline si le CSV source est absent."""
    if not cfg.source_path.is_file():
        raise FileNotFoundError(
            f"CSV source introuvable : '{cfg.source_path.resolve()}'. "
            "Lancez `make download` (ou `python scripts/download_raw_data.py`) "
            "pour récupérer les données brutes, ou ajustez INGESTION_RAW_DATA_DIR "
            "/ INGESTION_SOURCE_FILE dans votre .env."
        )


def _detect_encoding(path: Path) -> str:
    """Détecte l'encodage du fichier source (utf-8 validé d'abord, sinon chardet)."""
    with path.open("rb") as fh:
        sample = fh.read(_ENCODING_SAMPLE_SIZE)
    try:
        # utf-8 est auto-validant : un décodage strict réussi est fiable,
        # alors que chardet reste probabiliste sur un petit échantillon.
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as exc:
        if exc.start >= len(sample) - 3:
            # Erreur uniquement sur les derniers octets : caractère
            # multi-octets tronqué par l'échantillonnage, pas un faux utf-8.
            return "utf-8"
    return chardet.detect(sample).get("encoding") or "latin-1"


def _strip_column_spaces(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les espaces parasites dans les noms de colonnes (ex. 'NOM_HISTORIQUE ')."""
    raise NotImplementedError


def _add_metadata(df: pd.DataFrame, cfg: Settings) -> pd.DataFrame:
    """Ajoute record_hash, ingested_at (UTC), source_file, pipeline_version."""
    raise NotImplementedError


def _idempotence_filter(df: pd.DataFrame, previous_out: str) -> pd.DataFrame:
    """Retourne uniquement les lignes dont le hash diffère du run précédent."""
    raise NotImplementedError
