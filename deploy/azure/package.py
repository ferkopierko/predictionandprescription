"""Vytvorí ZIP pre App Service bez lokálnej databázy a vývojového prostredia."""

from pathlib import Path
import json
import os
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(os.environ.get("PAPU_PACKAGE_PATH", ROOT.parent / "hrontech-azure.zip"))
REQUIRED_DATA = [
    "vcdb_clean.csv", "vcdb_predikcie.csv", "vcdb_opatrenia_cis.csv",
    "vcdb_register_rizik.csv", "model_dopad_vcdb.joblib",
]
files = [ROOT / name for name in [".streamlit/config.toml", "deploy/azure/startup.sh"]]
files += [ROOT / "data/processed" / name for name in REQUIRED_DATA]
files += [p for folder in ["hrontech", "analysis/figures"] for p in (ROOT / folder).rglob("*")
          if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(ROOT).as_posix())
    archive.write(ROOT / "requirements.txt", "requirements.txt")
    revision = os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    archive.writestr("deployment.json", json.dumps({"revision": revision}))
print(f"{OUTPUT}: {OUTPUT.stat().st_size:,} bytes")
