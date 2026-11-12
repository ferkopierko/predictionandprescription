"""Stiahnutie a načítanie VERIS Community Database (VCDB)."""

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

# Verzia pripnutá na commit z 10. 11. 2026, aby boli výsledky opakovateľné
VCDB_COMMIT = "5ebf2f5be85d03ff7e7455f254a3e7d1d7fd671c"
VCDB_URL = f"https://raw.githubusercontent.com/vz-risk/VCDB/{VCDB_COMMIT}/data/joined/vcdb.json.zip"
VCDB_SHA256 = "e4be5dd432ccfad16520a6b60dd83e9d47c63b0f3352c26c4d43a5dd774c32c0"
VCDB_PATH = Path(__file__).parent / "data" / "raw" / "vcdb" / "vcdb.json.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_vcdb(path: Path = VCDB_PATH) -> Path:
    """Stiahne archív, ak chýba, a overí jeho kontrolný súčet."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".part")
        request = urllib.request.Request(VCDB_URL, headers={"User-Agent": "aispu-zadanie2/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as file:
            file.write(response.read())
        partial.replace(path)

    actual = sha256(path)
    if actual != VCDB_SHA256:
        raise ValueError(f"Neočakávaný SHA-256 súboru {path}: {actual}")
    return path


def load_incidents(path: Path = VCDB_PATH) -> list[dict]:
    """Vráti zoznam incidentov vo formáte VERIS JSON."""
    with zipfile.ZipFile(download_vcdb(path)) as archive:
        (name,) = archive.namelist()
        return json.loads(archive.read(name))


if __name__ == "__main__":
    incidents = load_incidents()
    print(f"Incidenty: {len(incidents)}")
