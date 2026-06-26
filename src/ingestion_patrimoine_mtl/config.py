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
    pipeline_version: str = Field(default="0.2.0")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="dev")  # "dev" | "json"

    @property
    def source_path(self) -> Path:
        return self.raw_data_dir / self.source_file

    @property
    def stage_01_out(self) -> Path:
        return self.data_dir / "01_raw" / "buildings_raw.parquet"

    @property
    def stage_02_out(self) -> Path:
        return self.data_dir / "02_clean" / "buildings_clean.parquet"

    @property
    def stage_03_out(self) -> Path:
        return self.data_dir / "03_normalized" / "buildings_normalized.parquet"

    @property
    def stage_04_out(self) -> Path:
        return self.data_dir / "04_enriched" / "buildings_enriched.jsonl"


settings = Settings()
