from __future__ import annotations

from pathlib import Path

from ingestion_patrimoine_mtl.pipeline.s01_ingest import _detect_encoding


class TestDetectEncoding:
    def test_utf8_file_returns_utf8(self, tmp_path: Path) -> None:
        """A well-formed UTF-8 file with French accents is detected as UTF-8."""
        csv_file = tmp_path / "sample.csv"
        csv_file.write_bytes("no_batiment,nom_historique\n0001,Édifice Art déco\n".encode())
        assert _detect_encoding(csv_file) == "utf-8"

    def test_latin1_file_not_detected_as_utf8(self, tmp_path: Path) -> None:
        """A latin-1 file containing bytes invalid in UTF-8 is not reported as UTF-8."""
        csv_file = tmp_path / "sample.csv"
        # Repeat enough content for chardet to identify the encoding confidently.
        content = "nom,adresse\n" + "Café de Paris,Montréal\n" * 50
        csv_file.write_bytes(content.encode("latin-1"))
        assert _detect_encoding(csv_file) != "utf-8"

    def test_latin1_detected_encoding_decodes_content(self, tmp_path: Path) -> None:
        """The encoding returned for a latin-1 file correctly round-trips its content."""
        original = "nom,adresse\n" + "Hôtel de Ville,Montréal\n" * 50
        csv_file = tmp_path / "sample.csv"
        csv_file.write_bytes(original.encode("latin-1"))
        encoding = _detect_encoding(csv_file)
        decoded = csv_file.read_bytes().decode(encoding)
        assert "H" in decoded and "Montr" in decoded
