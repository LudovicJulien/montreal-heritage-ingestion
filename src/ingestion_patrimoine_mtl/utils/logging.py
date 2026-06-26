from __future__ import annotations

import sys

from loguru import logger


def setup_logging(level: str = "INFO", fmt: str = "dev") -> None:
    """Configure loguru with the requested level and format.

    fmt="dev"  → coloured output to stderr (development)
    fmt="json" → structured JSON output to stderr (production / CI)
    """
    logger.remove()

    if fmt == "json":
        logger.add(sys.stderr, level=level, serialize=True)
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>"
            ),
            colorize=True,
        )
