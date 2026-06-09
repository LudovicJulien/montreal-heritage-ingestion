"""Test d'intégration — pipeline complet sur un échantillon de 10 enregistrements."""

from __future__ import annotations

import pytest


class TestPipelineE2E:
    @pytest.mark.skip(reason="à implémenter une fois les 4 stages opérationnels")
    def test_full_pipeline_produces_jsonl(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter une fois les 4 stages opérationnels")
    def test_output_record_count_matches_input(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter une fois les 4 stages opérationnels")
    def test_all_record_hashes_are_unique(self) -> None: ...

    @pytest.mark.skip(reason="à implémenter une fois les 4 stages opérationnels")
    def test_pipeline_is_idempotent(self) -> None: ...
