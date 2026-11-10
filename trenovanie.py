"""Stiahne aktuálne dáta z NVD a naučí prevádzkový model.

Spustenie:
    python trenovanie.py                 stiahne chýbajúce dáta a naučí model
    python trenovanie.py --download-only iba stiahne dáta
    python trenovanie.py --train-only    iba naučí model zo stiahnutých dát

Vyhodnotenie je časové: model sa učí na starších dátach, kalibruje sa na novších
a testuje na najnovších. Finálny model sa potom naučí aj na testovacom období.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, log_loss, precision_recall_fscore_support

import nvd
import opatrenia as op

CACHE_DIR = op.ROOT / "data" / "raw" / "nvd"
HISTORY_START = datetime(2022, 1, 1, tzinfo=timezone.utc)
TEST_DAYS = 120
CALIBRATION_DAYS = 180
N_JOBS = 12


def windows(start, end):
    current = start
    while current < end:
        following = min(current + timedelta(days=119), end)
        yield current, following
        current = following


def download(now):
    """Stiahne okná, ktoré ešte nie sú uložené. Posledné okno je vždy čerstvé."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for path in CACHE_DIR.glob("*_partial.csv.gz"):
        path.unlink()

    for start, end in windows(HISTORY_START, now):
        complete = end < now
        suffix = "" if complete else "_partial"
        path = CACHE_DIR / f"{start:%Y%m%d}_{end:%Y%m%d}{suffix}.csv.gz"
        if path.exists():
            print(f"{path.name}: už stiahnuté", flush=True)
            continue

        started = time.perf_counter()
        records = nvd.fetch_window(start, end)
        temporary = path.with_name(path.name + ".tmp")
        pd.DataFrame(records).to_csv(temporary, index=False, compression="gzip")
        temporary.replace(path)
        print(f"{path.name}: {len(records)} záznamov, {time.perf_counter() - started:.0f} s", flush=True)
        time.sleep(nvd.REQUEST_PAUSE)


def load_history():
    """Spojí pôvodný dataset s dátami z NVD a pripraví ich na modelovanie."""
    original = pd.read_csv(op.DATA_PATH).dropna(subset=["severity_v3"])
    original = pd.DataFrame({
        "cve_id": original["cve_id"],
        "description": original["description"],
        "cwe_text": original["cwe_ids"].fillna(""),
        "severity": original["severity_v3"],
        "published": pd.to_datetime(original["year"].astype(str) + "-01-01", utc=True),
        "label_type": "dataset",
    })

    frames = [pd.read_csv(path, keep_default_na=False) for path in sorted(CACHE_DIR.glob("*.csv.gz"))]
    if not frames:
        raise SystemExit("Chýbajú dáta z NVD. Spustite python trenovanie.py --download-only.")
    fresh = pd.concat(frames, ignore_index=True).drop_duplicates("cve_id", keep="last")
    downloaded = len(fresh)
    fresh = fresh[fresh["severity"].isin(op.LABELS) & fresh["description"].ne("") & fresh["vuln_status"].ne("Rejected")].copy()
    print(f"Z NVD: {downloaded} záznamov, s hodnotením CVSS v3: {len(fresh)}", flush=True)
    fresh["published"] = pd.to_datetime(fresh["published"], utc=True)

    data = pd.concat([
        original[~original["cve_id"].isin(fresh["cve_id"])],
        fresh[list(original.columns)],
    ], ignore_index=True)
    has_leakage = data["description"].str.contains(op.LEAKAGE_PATTERN, case=False, regex=True)
    print(f"Vylúčené pre únik cieľa: {int(has_leakage.sum())}", flush=True)
    data = data[~has_leakage].sort_values("published").reset_index(drop=True)
    data["target"] = pd.Categorical(data["severity"], categories=op.LABELS, ordered=True).codes
    return data


def evaluate(bundle, test):
    probabilities = op.predict_probabilities(bundle, test)
    predicted = probabilities.argmax(axis=1)
    truth = test["target"].to_numpy()
    critical = op.LABELS.index("CRITICAL")
    precision, recall, _, _ = precision_recall_fscore_support(truth, predicted, labels=[critical], zero_division=0)
    actions, _ = op.choose_actions(probabilities)
    return {
        "záznamy": int(len(test)),
        "macro_f1": float(f1_score(truth, predicted, average="macro", labels=[0, 1, 2, 3], zero_division=0)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "recall_critical": float(recall[0]),
        "precision_critical": float(precision[0]),
        "log_loss": float(log_loss(truth, probabilities, labels=[0, 1, 2, 3])),
        "opatrenia_podiel": {
            name: float((actions == index).mean()) for index, name in enumerate(op.ACTION_NAMES)
        },
    }


def train(now):
    data = load_history()
    test_start = pd.Timestamp(now - timedelta(days=TEST_DAYS))
    calibration_start = test_start - pd.Timedelta(days=CALIBRATION_DAYS)

    past = data[data["published"] < calibration_start]
    calibration = data[(data["published"] >= calibration_start) & (data["published"] < test_start)]
    test = data[data["published"] >= test_start]
    print(f"Tréning: {len(past)}, kalibrácia: {len(calibration)}, test: {len(test)}", flush=True)

    started = time.perf_counter()
    candidate = op.fit_bundle(past, calibration, n_jobs=N_JOBS)
    print(f"Skúšobný model hotový za {time.perf_counter() - started:.0f} s", flush=True)

    report = {
        "natrenovane": now.strftime("%Y-%m-%d %H:%M UTC"),
        "testovacie_obdobie_od": f"{test_start:%Y-%m-%d}",
        "treningove_zaznamy_finalny_model": int(len(data[data["published"] < test_start])),
        "kalibracne_zaznamy_finalny_model": int(len(test)),
        "novy_model": evaluate(candidate, test),
        "novy_model_iba_hodnotenie_nvd": evaluate(candidate, test[test["label_type"] == "Primary"]),
        "novy_model_iba_hodnotenie_cna": evaluate(candidate, test[test["label_type"] == "Secondary"]),
    }
    if op.MODEL_PATH.exists():
        report["povodny_model_do_2018"] = evaluate(joblib.load(op.MODEL_PATH), test)

    started = time.perf_counter()
    final = op.fit_bundle(data[data["published"] < test_start], test, n_jobs=N_JOBS)
    print(f"Finálny model hotový za {time.perf_counter() - started:.0f} s", flush=True)
    op.save_bundle(final, op.PRODUCTION_MODEL_PATH)

    partial = op.PRODUCTION_REPORT_PATH.with_suffix(".part")
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    partial.replace(op.PRODUCTION_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--train-only", action="store_true")
    arguments = parser.parse_args()

    moment = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if not arguments.train_only:
        download(moment)
    if not arguments.download_only:
        train(moment)
