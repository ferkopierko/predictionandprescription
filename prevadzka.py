"""Priebežné spracovanie nových zraniteľností z NVD.

Proces v pravidelnom intervale stiahne nové a zmenené CVE, nové vyhodnotí aktuálnym
modelom a výsledky uloží do databázy SQLite, z ktorej číta aplikácia.
Spustenie: python prevadzka.py
"""

import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import nvd
import opatrenia as op

DB_PATH = Path(os.environ.get("PREVADZKA_DB", op.ROOT / "data" / "processed" / "prevadzka.db"))
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "900"))
SEED_HOURS = int(os.environ.get("SEED_HOURS", "24"))
OVERLAP = timedelta(minutes=2)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cve_live (
    cve_id TEXT PRIMARY KEY,
    published TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    vuln_status TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT NOT NULL,
    cwe_text TEXT NOT NULL,
    p_low REAL NOT NULL,
    p_medium REAL NOT NULL,
    p_high REAL NOT NULL,
    p_critical REAL NOT NULL,
    predicted_class TEXT NOT NULL,
    expected_risk REAL NOT NULL,
    action TEXT NOT NULL,
    actual_severity TEXT,
    label_type TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    model TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cve_live_published ON cve_live (published);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def utc_now():
    return datetime.now(timezone.utc)


def format_time(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(SCHEMA)
    return connection


def get_state(connection, key):
    row = connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_states(connection, **values):
    connection.executemany(
        "INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        [(key, str(value)) for key, value in values.items()],
    )
    connection.commit()


def _parse_time(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def process_records(connection, bundle, model_name, records, seed_start):
    """Nové záznamy vyhodnotí a pri známych doplní zmeny. Vráti počet nových."""
    usable = [
        record for record in records
        if record["description"]
        and record["vuln_status"] != "Rejected"
        and _parse_time(record["published"]) >= seed_start
    ]
    # NVD môže v prekrývajúcich sa oknách vrátiť ten istý záznam viackrát
    usable = list({record["cve_id"]: record for record in usable}.values())
    known = {row[0] for row in connection.execute("SELECT cve_id FROM cve_live")}
    new_records = [record for record in usable if record["cve_id"] not in known]

    connection.executemany(
        "UPDATE cve_live SET last_modified = ?, vuln_status = ?, actual_severity = ?, label_type = ? WHERE cve_id = ?",
        [
            (record["last_modified"], record["vuln_status"], record["severity"], record["label_type"], record["cve_id"])
            for record in usable if record["cve_id"] in known
        ],
    )
    connection.execute(
        "DELETE FROM cve_live WHERE cve_id IN (SELECT value FROM json_each(?))",
        (pd.Series([record["cve_id"] for record in records if record["vuln_status"] == "Rejected"], dtype=str).to_json(orient="values"),),
    )

    if new_records:
        frame = pd.DataFrame(new_records)
        probabilities = op.predict_probabilities(bundle, frame[["description", "cwe_text"]])
        actions, expected_risk = op.choose_actions(probabilities)
        processed_at = format_time(utc_now())
        connection.executemany(
            "INSERT INTO cve_live VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    record["cve_id"], record["published"], record["last_modified"], record["vuln_status"],
                    record["source"], record["description"], record["cwe_text"],
                    *[float(value) for value in probabilities[index]],
                    op.LABELS[int(probabilities[index].argmax())],
                    float(expected_risk[index]),
                    op.ACTION_NAMES[int(actions[index])],
                    record["severity"], record["label_type"], processed_at, model_name,
                )
                for index, record in enumerate(new_records)
            ],
        )
    connection.commit()
    return len(new_records)


def poll_once(connection, bundle, model_name):
    now = utc_now()
    seed_value = get_state(connection, "seed_start")
    if seed_value is None:
        seed_value = format_time(now - timedelta(hours=SEED_HOURS))
        set_states(connection, seed_start=seed_value)
    seed_start = _parse_time(seed_value)

    checkpoint = get_state(connection, "checkpoint")
    since = (_parse_time(checkpoint) - OVERLAP) if checkpoint else seed_start
    since = max(since, now - timedelta(days=119))

    records = nvd.fetch_window(since, now, field="lastMod")
    added = process_records(connection, bundle, model_name, records, seed_start)
    # Kontrolný bod sa posunie až po úspešnom uložení, výpadok teda nič nevynechá
    set_states(connection, checkpoint=format_time(now), last_success=format_time(utc_now()), last_error="")
    return added, len(records)


def run():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    connection = connect()
    set_states(connection, poll_seconds=POLL_SECONDS)
    bundle, loaded_key, model_name = None, None, ""

    while True:
        try:
            path = op.active_model_path()
            key = (str(path), path.stat().st_mtime) if path.exists() else None
            if bundle is None or key != loaded_key:
                bundle = op.load_active()
                path = op.active_model_path()
                loaded_key = (str(path), path.stat().st_mtime)
                model_name = f"{path.stem} ({datetime.fromtimestamp(path.stat().st_mtime, timezone.utc):%Y-%m-%d %H:%M} UTC)"
                print(f"Načítaný model: {model_name}", flush=True)

            set_states(connection, last_attempt=format_time(utc_now()), model=model_name)
            added, seen = poll_once(connection, bundle, model_name)
            print(f"{format_time(utc_now())} prijaté z NVD: {seen}, nové: {added}", flush=True)
        except Exception as error:  # Prevádzka musí prežiť výpadok NVD a skúsiť to znova
            print(f"{format_time(utc_now())} chyba: {error!r}", flush=True)
            set_states(connection, last_error=f"{format_time(utc_now())}: {type(error).__name__}: {error}"[:400])
        time.sleep(POLL_SECONDS)


def read_status(path=DB_PATH):
    """Vráti stav prevádzky pre aplikáciu alebo None, ak ešte nebežala."""
    if not path.exists():
        return None
    connection = connect(path)
    try:
        return dict(connection.execute("SELECT key, value FROM state").fetchall())
    finally:
        connection.close()


def read_records(path=DB_PATH):
    connection = connect(path)
    try:
        return pd.read_sql_query("SELECT * FROM cve_live ORDER BY published DESC", connection)
    finally:
        connection.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run()
