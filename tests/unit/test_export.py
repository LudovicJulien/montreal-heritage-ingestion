"""Unit tests — stage 06 · Export (front-end artifacts)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s06_export import (
    BUILDINGS_GEOJSON_FILENAME,
    BUILDINGS_JSON_FILENAME,
    MONTREAL_URL_TEMPLATE,
    STATS_JSON_FILENAME,
    run,
)
from ingestion_patrimoine_mtl.utils.geo import is_in_montreal_bbox


class TestCoordinates:
    def test_latitude_longitude_not_swapped(self, export_source: Settings) -> None:
        """A Montreal building's mapped lat/lon land inside the Montreal bbox, not swapped."""
        public = run(export_source)

        building = public.set_index("id").loc["0039-27-4599-00"]
        latitude = float(building["latitude"])
        longitude = float(building["longitude"])
        assert latitude == pytest.approx(45.5017)
        assert longitude == pytest.approx(-73.5679)
        assert is_in_montreal_bbox(latitude, longitude)


class TestGeoJson:
    def test_geojson_validates_as_a_feature_collection(self, export_source: Settings) -> None:
        """buildings.geojson is a FeatureCollection whose Features carry Point geometries."""
        run(export_source)

        geojson = json.loads((export_source.stage_06_out / BUILDINGS_GEOJSON_FILENAME).read_text())

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) > 0
        for feature in geojson["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"
            assert len(feature["geometry"]["coordinates"]) == 2

    def test_record_without_coordinates_excluded_kept_in_buildings_json(
        self, export_source: Settings
    ) -> None:
        """The building with no centro_x/centro_y is absent from the GeoJSON, present in buildings.json."""
        run(export_source)

        geojson = json.loads((export_source.stage_06_out / BUILDINGS_GEOJSON_FILENAME).read_text())
        buildings = json.loads((export_source.stage_06_out / BUILDINGS_JSON_FILENAME).read_text())

        geojson_ids = {feature["properties"]["id"] for feature in geojson["features"]}
        building_ids = {building["id"] for building in buildings}

        assert "0039-28-0003-00" not in geojson_ids
        assert "0039-28-0003-00" in building_ids


class TestMontrealUrl:
    def test_url_built_from_identifier_no_request_made(self, export_source: Settings) -> None:
        """url_montreal is a deterministic string built from the identifier — no HTTP call."""
        public = run(export_source)

        building = public.set_index("id").loc["0039-27-4599-00"]
        assert building["url_montreal"] == MONTREAL_URL_TEMPLATE.format(id="0039-27-4599-00")


class TestStats:
    def test_stats_totals_reconcile_with_source_frame(self, export_source: Settings) -> None:
        """total_buildings, buildings_with_coordinates and facet sums match the source frame."""
        public = run(export_source)

        stats = json.loads((export_source.stage_06_out / STATS_JSON_FILENAME).read_text())

        assert stats["total_buildings"] == len(public)
        assert stats["buildings_with_coordinates"] == int(public["latitude"].notna().sum())
        assert sum(stats["by_arrondissement"].values()) == len(public)


class TestProvenance:
    def _stats(self, cfg: Settings) -> dict[str, object]:
        run(cfg)
        return json.loads((cfg.stage_06_out / STATS_JSON_FILENAME).read_text())  # type: ignore[no-any-return]

    def _write_metadata(self, cfg: Settings, content: str) -> None:
        cfg.source_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.source_metadata_path.write_text(content, encoding="utf-8")

    def test_source_updated_at_read_from_sidecar_as_utc(self, export_source: Settings) -> None:
        """A naive portal timestamp is read as UTC and written ISO 8601 with a Z suffix."""
        self._write_metadata(export_source, '{"source_updated_at": "2025-06-19T14:26:38.924807"}')

        assert self._stats(export_source)["source_updated_at"] == "2025-06-19T14:26:38Z"

    def test_source_updated_at_null_when_sidecar_absent(self, export_source: Settings) -> None:
        """No sidecar file: the export succeeds and source_updated_at is null."""
        assert not export_source.source_metadata_path.exists()

        assert self._stats(export_source)["source_updated_at"] is None

    @pytest.mark.parametrize(
        "content",
        ['{"source_updated_at": null}', "{}", "not json", '{"source_updated_at": "soon"}'],
    )
    def test_source_updated_at_null_when_sidecar_unusable(
        self, export_source: Settings, content: str
    ) -> None:
        """A null, missing, malformed or unparsable date degrades to null, never raises."""
        self._write_metadata(export_source, content)

        assert self._stats(export_source)["source_updated_at"] is None

    def test_exported_at_derives_from_ingested_at_not_the_clock(
        self, export_source: Settings
    ) -> None:
        """exported_at is the corpus's latest ingested_at, so reruns give identical bytes."""
        stamp = pd.Timestamp("2026-09-27 19:29:19.971768")
        merged = pd.read_parquet(export_source.stage_04_out)
        merged["ingested_at"] = stamp
        merged.to_parquet(export_source.stage_04_out, index=False)

        first = self._stats(export_source)
        stats_path = export_source.stage_06_out / STATS_JSON_FILENAME
        first_bytes = stats_path.read_bytes()
        self._stats(export_source)

        assert first["exported_at"] == "2026-09-27T19:29:19Z"
        assert stats_path.read_bytes() == first_bytes

    def test_exported_at_null_without_ingested_at(self, export_source: Settings) -> None:
        """A merged frame without ingested_at yields a null exported_at."""
        merged = pd.read_parquet(export_source.stage_04_out)
        assert "ingested_at" not in merged.columns

        assert self._stats(export_source)["exported_at"] is None

    def test_existing_stats_keys_unchanged_and_new_keys_last(self, export_source: Settings) -> None:
        """Provenance fields are appended after the existing keys, which keep their order."""
        keys = list(self._stats(export_source))

        assert keys == [
            "total_buildings",
            "buildings_with_coordinates",
            "by_arrondissement",
            "by_decade",
            "by_typologie",
            "by_statut_juridique",
            "source_updated_at",
            "exported_at",
        ]


class TestRun:
    def test_run_writes_the_three_artifacts(self, export_source: Settings) -> None:
        """run() writes buildings.geojson, buildings.json and stats.json under stage_06_out."""
        run(export_source)

        for filename in (BUILDINGS_GEOJSON_FILENAME, BUILDINGS_JSON_FILENAME, STATS_JSON_FILENAME):
            assert (export_source.stage_06_out / filename).is_file()
