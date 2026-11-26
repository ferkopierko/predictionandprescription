"""Overí verejnú simuláciu a hodnotenie; uprace iba vlastné testovacie záznamy."""

import sys
from pathlib import Path
from functools import partial

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from provision_sql import admin_connection
from scripts.simulacia import call as api_call, incident_body

call = partial(api_call, timeout=60)
BASE = "https://safetyfirst-hrontech-54c15147.azurewebsites.net"
original = call("GET", BASE + "/api/hodnotenia")
case = call("POST", BASE + "/api/firma/simulacia", {"scenario": "portal"})
record_id = None
try:
    body = incident_body(case)
    body["nazov"] = "Overenie webu pre kolegov"
    result = call("POST", BASE + "/api/hodnotenie", body)
    record_id = result["id"]
    saved = next(row for row in call("GET", BASE + "/api/hodnotenia") if row["id"] == record_id)
    assert saved["asset_id"] == case["asset_id"] and saved["case_id"] == case["id"]
    assert saved["nazov"] == body["nazov"]
    print("Verejne API: simulacia, predikcia, zapis cez identitu aplikacie a citanie OK", flush=True)
finally:
    with admin_connection() as db:
        if record_id:
            db.execute("DELETE FROM hodnotenia WHERE id=?", (record_id,))
            db.execute("DELETE FROM company_events WHERE kind=? AND detail LIKE ?", ("Hodnotenie", f"Hodnotenie č. {record_id}:%"))
        db.execute("DELETE FROM company_cases WHERE id=?", (case["id"],))
        db.execute("DELETE FROM company_events WHERE kind=? AND detail LIKE ?", ("Simulácia", f"Incident č. {case['id']}:%"))
remaining = call("GET", BASE + "/api/hodnotenia")
assert {row["id"] for row in original} <= {row["id"] for row in remaining}
assert record_id not in {row["id"] for row in remaining}
print("Vlastne testovacie zaznamy upratane; prenesene hodnotenia zachovane", flush=True)
