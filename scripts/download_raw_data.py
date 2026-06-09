"""Download raw heritage data from Données Montréal open data portal."""

import hashlib
import sys
from pathlib import Path

import requests

URL = "https://donnees.montreal.ca/dataset/607c00db-0446-4389-9cdc-d8127f8da57a/resource/a89dd7ad-ebb1-4d1e-97d5-e14724e50447/download/edifices_patrimoine.csv"
DEST = Path("rawData/edifices_patrimoine.csv")


def download() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {URL} ...")
    with requests.get(URL, stream=True, timeout=30) as response:
        response.raise_for_status()
        sha256 = hashlib.sha256()
        with DEST.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                sha256.update(chunk)

    size_kb = DEST.stat().st_size // 1024
    print(f"Saved {DEST} ({size_kb} KB) — sha256: {sha256.hexdigest()[:16]}...")


if __name__ == "__main__":
    try:
        download()
    except requests.HTTPError as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)
