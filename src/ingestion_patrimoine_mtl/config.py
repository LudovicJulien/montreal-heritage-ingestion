from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    raw_data_dir: Path = Field(default=Path("rawData"))
    data_dir: Path = Field(default=Path("data"))
    source_file: str = Field(default="edifices_patrimoine.csv")
    # RPCQ open data exports (stage 01b), published as two separate Données Québec
    # resources: immeubles classés by the ministry, immeubles cités by municipalities.
    rpcq_subdir: str = Field(default="rpcq")
    rpcq_classes_file: str = Field(default="immeubles_classes.csv")
    rpcq_cites_file: str = Field(default="immeubles_cites.csv")
    pipeline_version: str = Field(default="0.4.0")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="dev")  # "dev" | "json"

    @property
    def source_path(self) -> Path:
        return self.raw_data_dir / self.source_file

    @property
    def rpcq_source_dir(self) -> Path:
        """Directory holding both RPCQ exports, derived from raw_data_dir.

        Derived rather than configured on its own so that pointing raw_data_dir at a
        temporary directory relocates the RPCQ sources with it, exactly like source_path.
        """
        return self.raw_data_dir / self.rpcq_subdir

    @property
    def rpcq_classes_path(self) -> Path:
        return self.rpcq_source_dir / self.rpcq_classes_file

    @property
    def rpcq_cites_path(self) -> Path:
        return self.rpcq_source_dir / self.rpcq_cites_file

    @property
    def stage_01_out(self) -> Path:
        return self.data_dir / "01_raw" / "buildings_raw.parquet"

    @property
    def stage_01b_out(self) -> Path:
        return self.data_dir / "01b_rpcq" / "rpcq_raw.parquet"

    @property
    def stage_02_out(self) -> Path:
        return self.data_dir / "02_clean" / "buildings_clean.parquet"

    @property
    def stage_03_out(self) -> Path:
        return self.data_dir / "03_normalized" / "buildings_normalized.parquet"

    @property
    def stage_05_out(self) -> Path:
        return self.data_dir / "05_enriched" / "buildings_enriched.jsonl"


settings = Settings()
