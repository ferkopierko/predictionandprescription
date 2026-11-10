"""Stiahnutie a načítanie datasetu CVE/CWE pre Threat Modeling and Risk Assessment."""

import hashlib
import urllib.request
from pathlib import Path

import pandas as pd

DATASET_URL = (
    "https://huggingface.co/datasets/zefang-liu/cve-and-cwe-mapping-dataset/"
    "resolve/89e468befa6b62034d47ead1293dca34f6da4889/Global_Dataset.csv"
)
DATASET_SHA256 = "fd691eed907a7e15fbc4f0943b3a27da770b5bb022ccc1aa62fcb8babe5f3890"
DATASET_PATH = Path(__file__).parent / "data" / "raw" / "Global_Dataset.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(path: Path = DATASET_PATH) -> Path:
    """Stiahne dataset, ak chýba, a overí jeho kontrolný súčet."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(DATASET_URL, partial)
        partial.replace(path)

    actual = sha256(path)
    if actual != DATASET_SHA256:
        raise ValueError(f"Neočakávaný SHA-256 súboru {path}: {actual}")
    return path


def load_raw(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Načíta surové dáta. Text 'None' v CSV znamená chýbajúcu hodnotu."""
    return pd.read_csv(
        download_dataset(path),
        encoding="utf-8-sig",
        na_values=["None"],
    )


if __name__ == "__main__":
    df = load_raw()
    print(f"Záznamy: {len(df)}, stĺpce: {list(df.columns)}")
    print(df.dtypes)
    print(df.isna().sum())
