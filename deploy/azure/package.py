"""Vytvorí ZIP pre App Service bez lokálnej databázy a vývojového prostredia."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT.parent / "hrontech-azure.zip"
REQUIRED_DATA = [
    "vcdb_clean.csv", "vcdb_predikcie.csv", "vcdb_opatrenia_cis.csv",
    "vcdb_register_rizik.csv", "model_dopad_vcdb.joblib",
]
files = [ROOT / name for name in [
    "app.py", "api.py", "azure_app.py", "opatrenia.py", "preklady.py", "simulacia.py", "vcdb_model.py",
    "frontend.py", "firma.py", "firma_ui.py",
    ".streamlit/config.toml", "deploy/azure/startup.sh",
]]
files += [ROOT / "data/processed" / name for name in REQUIRED_DATA]
files += [p for folder in ["static", "figures"] for p in (ROOT / folder).rglob("*") if p.is_file()]
with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(ROOT).as_posix())
    archive.write(ROOT / "deploy/azure/requirements.txt", "requirements.txt")
print(f"{OUTPUT}: {OUTPUT.stat().st_size:,} bytes")
