"""Skutočné SQL operácie vrátane väzieb a transakcie firemného hodnotenia."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import firma as co
import opatrenia as op
from provision_sql import admin_connection

assert op.uses_azure_sql(), "Nastavte AZURE_SQL_CONNECTION_STRING pre databazu papu-hrontech"
original = co.profile()
counts = (len(co.assets()), len(co.findings()), len(co.assessments()), len(co.cases()))
with admin_connection() as connection:
    last_event = connection.execute("SELECT COALESCE(MAX(id),0) FROM company_events").fetchone()[0]
asset_id = finding_id = case_id = record_id = None
try:
    asset_id = co.add_asset("Overenie Azure čľšťž", "Servery", 1, "test.hrontech.example", "Linux", "IT", "Stredná", "S - Web application")
    finding_id = co.add_finding(asset_id, "Overenie SQL", "Stredná", "Overiť uloženie a väzby.", 500, "web")
    co.set_finding_status(finding_id, "V riešení", "Diakritika čľšťž")
    assert co.finding(finding_id)["note"] == "Diakritika čľšťž"
    case = co.start_simulation("web", finding_id)
    case_id = case["id"]
    record_id, result = co.assess_and_save(case["input"], asset_id, .25, "Overenie SQL", finding_id, case_id)
    saved = co.assessments().loc[lambda frame: frame.id == record_id].iloc[0]
    assert saved.asset_id == asset_id and saved.finding_id == finding_id
    assert co.cases().loc[lambda frame: frame.id == case_id].iloc[0].status == "Vyhodnotený"
    assert co.asset(asset_id)["name"] == "Overenie Azure čľšťž"
    assert len(co.risk_register()) == 7
    assert not co.events().empty
    co.update_settings(original["budget"] + 1, original["losses"], original["cost_factor"], original["horizon"])
    assert co.profile()["budget"] == original["budget"] + 1
    op.delete_assessments([record_id])
    with admin_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM company_assessments WHERE assessment_id=?", (record_id,)).fetchone()[0] == 0
    print("Azure SQL: inventar, zistenia, simulacia, hodnotenie, nastavenia a kaskadove mazanie OK", flush=True)
finally:
    co.update_settings(original["budget"], original["losses"], original["cost_factor"], original["horizon"])
    with admin_connection() as connection:
        if record_id:
            connection.execute("DELETE FROM hodnotenia WHERE id=?", (record_id,))
        if case_id:
            connection.execute("DELETE FROM company_cases WHERE id=?", (case_id,))
        if finding_id:
            connection.execute("DELETE FROM company_findings WHERE id=?", (finding_id,))
        if asset_id:
            connection.execute("DELETE FROM company_assets WHERE id=?", (asset_id,))
        connection.execute("DELETE FROM company_events WHERE id>?", (last_event,))
assert (len(co.assets()), len(co.findings()), len(co.assessments()), len(co.cases())) == counts
assert co.profile() == original
print("Povodny preneseny stav zostal zachovany", flush=True)
