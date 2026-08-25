"""Download the two RPCQ open data exports from the Données Québec portal.

Both resources are published by the Ministère de la Culture et des Communications
under CC-BY 4.0 and cover only the *legally protected* heritage properties:

- immeubles patrimoniaux **classés** by the minister (updated 2026-05-11)
- immeubles patrimoniaux **cités** by municipalities and Indigenous communities
  (updated 2023-06-26)

The rest of the RPCQ exists only on patrimoine-culturel.gouv.qc.ca. See ADR-005.
"""

import hashlib
import sys
from pathlib import Path

import requests

DEST_DIR = Path("rawData/rpcq")

RESOURCES = {
    "immeubles_classes.csv": (
        "https://www.donneesquebec.ca/recherche/dataset/"
        "33a72ee0-4af3-4d76-8a13-0338e10cdaeb/resource/"
        "c6c20af9-504f-4848-9ff2-32c463c9b04c/download/ip_tp_xsl.csv"
    ),
    "immeubles_cites.csv": (
        "https://www.donneesquebec.ca/recherche/dataset/"
        "c3d54554-6f25-4117-a573-cf21dcdc9644/resource/"
        "ba6bed2e-2b87-47fa-be28-681be1b4b649/download/donneesouvertesmccipciv3.csv"
    ),
}


def download_one(filename: str, url: str) -> None:
    dest = DEST_DIR / filename

    print(f"Downloading {url} ...")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        sha256 = hashlib.sha256()
        with dest.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                sha256.update(chunk)

    size_kb = dest.stat().st_size // 1024
    print(f"Saved {dest} ({size_kb} KB) — sha256: {sha256.hexdigest()[:16]}...")


def download() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in RESOURCES.items():
        download_one(filename, url)


if __name__ == "__main__":
    try:
        download()
    except requests.HTTPError as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)
