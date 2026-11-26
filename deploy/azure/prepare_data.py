"""Pripraví chýbajúce výstupy VCDB pre čistý GitHub runner."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["vcdb_clean.csv", "vcdb_predikcie.csv", "vcdb_opatrenia_cis.csv",
            "vcdb_register_rizik.csv", "model_dopad_vcdb.joblib"]

if not all((ROOT / "data/processed" / name).is_file() for name in REQUIRED):
    for notebook in ["priprava_dat.ipynb", "predikcia.ipynb", "preskriptivna_udrzba.ipynb"]:
        import nbformat
        from nbclient import NotebookClient

        print(f"Spustam {notebook}", flush=True)
        content = nbformat.read(ROOT / "analysis" / notebook, as_version=4)
        NotebookClient(content, timeout=1800, kernel_name="python3",
                       resources={"metadata": {"path": str(ROOT)}}).execute()
    # Runtime data are regenerated, while published illustrations stay as committed.
    subprocess.run(["git", "restore", "--", "analysis/figures"], cwd=ROOT, check=True)
for name in REQUIRED:
    path = ROOT / "data/processed" / name
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"Chyba vystup {path}")
print("Vsetky vystupy VCDB su pripravene")
