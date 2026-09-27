"""Unit tests — stage 06 · Export (front-end artifacts)."""

from __future__ import annotations

import json

import pytest

from ingestion_patrimoine_mtl.config import Settings
from ingestion_patrimoine_mtl.pipeline.s06_export import (
    BUILDINGS_GEOJSON_FILENAME,
    BUILDINGS_JSON_FILENAME,
    MONTREAL_URL_TEMPLATE,
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
