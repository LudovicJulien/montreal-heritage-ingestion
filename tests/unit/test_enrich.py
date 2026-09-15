"""Unit tests — stage 05 · Enrich (taxonomy + NER spaCy)."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
import pytest
from loguru import logger

from ingestion_patrimoine_mtl.pipeline.s05_enrich import _normalize_typologie


@pytest.fixture
def captured_warnings() -> Iterator[list[str]]:
    """Collect the WARNING lines a call emits.

    loguru does not go through the stdlib logging module, so caplog sees
    nothing; a sink is the only way to assert on what the stage told the
    operator.
    """
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(message), level="WARNING")
    try:
        yield messages
    finally:
        logger.remove(sink_id)


class TestNormalizeTypologie:
    def test_source_column_survives_normalization(self) -> None:
        """typologie_specifique is untouched — the mapped value lives in its own column."""
        df = pd.DataFrame({"typologie_specifique": ["École", "non applicable"]})

        result = _normalize_typologie(df)

        assert result["typologie_specifique"].tolist() == ["École", "non applicable"]

    def test_typologie_normalisee_is_added(self) -> None:
        """The new column carries the mapped value, sentinel and duplicate cases included."""
        df = pd.DataFrame(
            {
                "typologie_specifique": [
                    "École",
                    "non applicable",
                    "Édifice de culte",
                    "Édifice religieux",
                ]
            }
        )

        result = _normalize_typologie(df)

        assert result["typologie_normalisee"].tolist() == [
            "école",
            None,
            "édifice religieux",
            "édifice religieux",
        ]

    def test_null_typologie_specifique_stays_null(self) -> None:
        """A missing typologie_specifique produces a missing typologie_normalisee, not a crash."""
        df = pd.DataFrame({"typologie_specifique": [None]})

        result = _normalize_typologie(df)

        assert result["typologie_normalisee"].iloc[0] is None

    def test_unmapped_value_logs_once_at_warning(self, captured_warnings: list[str]) -> None:
        """A raw value TYPOLOGIE_MAPPING has never seen is logged once, not once per row."""
        df = pd.DataFrame({"typologie_specifique": ["Phare maritime", "Phare maritime"]})

        _normalize_typologie(df)

        matching = [message for message in captured_warnings if "Phare maritime" in message]
        assert len(matching) == 1

    def test_known_value_does_not_log(self, captured_warnings: list[str]) -> None:
        """A raw value already in TYPOLOGIE_MAPPING is not a review case."""
        df = pd.DataFrame({"typologie_specifique": ["École"]})

        _normalize_typologie(df)

        assert captured_warnings == []


class TestExtractEntities:
    @pytest.mark.skip(reason="implement with s05_enrich + spaCy")
    def test_extracts_person_from_known_text(self) -> None: ...

    @pytest.mark.skip(reason="implement with s05_enrich + spaCy")
    def test_returns_empty_entities_for_none_text(self) -> None: ...

    @pytest.mark.skip(reason="implement with s05_enrich + spaCy")
    def test_extracts_historical_date(self) -> None: ...
