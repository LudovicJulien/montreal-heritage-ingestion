from __future__ import annotations

import argparse
import sys

from ingestion_patrimoine_mtl.config import settings
from ingestion_patrimoine_mtl.utils.logging import setup_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingestion-patrimoine-mtl",
        description="Pipeline d'ingestion RAG — Édifices patrimoniaux de Montréal",
    )
    parser.add_argument(
        "--stage",
        choices=["01", "02", "03", "04", "all"],
        default="all",
        help="Étape du pipeline à exécuter (défaut : all)",
    )
    parser.add_argument(
        "--log-level",
        default=settings.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--log-format",
        default=settings.log_format,
        choices=["dev", "json"],
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    setup_logging(level=args.log_level, fmt=args.log_format)

    from ingestion_patrimoine_mtl.pipeline import s01_ingest, s02_clean, s03_normalize, s04_enrich

    stages = {
        "01": s01_ingest.run,
        "02": s02_clean.run,
        "03": s03_normalize.run,
        "04": s04_enrich.run,
    }

    to_run = list(stages.keys()) if args.stage == "all" else [args.stage]

    for stage_id in to_run:
        stages[stage_id](cfg=settings)

    return 0


if __name__ == "__main__":
    sys.exit(main())
