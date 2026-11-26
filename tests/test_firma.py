import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import firma as co
import opatrenia as op
import pandas as pd


class CompanyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "company.db"
        self.database_patch = patch.object(op, "DB_PATH", self.database)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.directory.cleanup()

    def test_seed_is_idempotent_and_findings_reference_real_inventory(self):
        self.assertEqual(co.profile()["employees"], 82)
        self.assertEqual(len(co.assets()), 15)
        self.assertEqual(len(co.assets()), 15)
        findings = co.findings()
        self.assertEqual(len(findings), 14)
        self.assertTrue(set(findings.asset_id) <= set(co.assets().id))
        self.assertEqual(co.finding("SIM-011")["scenario"], "loss")

    def test_simulated_case_is_assessed_saved_and_linked(self):
        case = co.start_simulation("portal")
        record_id, result = co.assess_and_save(case["input"], case["asset_id"], case["frequency"],
                                             case["title"], case["finding_id"], case["id"])
        self.assertEqual(co.cases().iloc[0].status, "Vyhodnotený")
        saved = co.assessments().iloc[0]
        self.assertEqual(saved.id, record_id)
        self.assertEqual(saved.asset_id, "WEB-02")
        self.assertEqual(saved.finding_id, "SIM-001")
        self.assertAlmostEqual(sum(result["pravdepodobnosti"].values()), 1)
        self.assertEqual(result["opatrenie"], min(result["porovnanie"], key=lambda row: row["celkove_naklady"])["opatrenie"])
        self.assertEqual(json.loads(saved.vstup)["odvetvie"], "Výroba")

    def test_economics_affect_loss_but_not_the_learned_probabilities(self):
        incident = co.incident_input("WEB-02", "portal")
        first = co.assess(incident, .35)
        co.update_settings(1000, [10000, 100000, 1000000], .35, 3)
        second = co.assess(incident, .35)
        self.assertEqual(first["pravdepodobnosti"], second["pravdepodobnosti"])
        self.assertAlmostEqual(second["ocakavana_strata"], first["ocakavana_strata"] * 2)
        self.assertFalse(second["within_budget"])

    def test_saved_assumptions_remain_a_snapshot_after_settings_change(self):
        incident = co.incident_input("WEB-02", "portal")
        record_id, _ = co.assess_and_save(incident, "WEB-02", .35)
        co.update_settings(10000, [10000, 100000, 1000000], .5, 4)
        with co.db() as connection:
            stored = json.loads(connection.execute("SELECT assumptions FROM company_assessments WHERE assessment_id=?", (record_id,)).fetchone()[0])
        self.assertEqual(stored["budget"], 45000)
        self.assertEqual(stored["losses"], [5000, 50000, 500000])

    def test_company_history_excludes_legacy_generic_assessments(self):
        incident = co.incident_input("WEB-02", "portal")
        op.save_assessment(incident, op.assess(incident, .35), "legacy")
        self.assertEqual(len(op.load_assessments()), 1)
        self.assertTrue(co.assessments().empty)

    def test_invalid_links_do_not_create_partial_assessments(self):
        case = co.start_simulation("portal")
        with self.assertRaises(ValueError):
            co.assess_and_save(case["input"], "WEB-02", .35, finding_id="SIM-003")
        with self.assertRaises(ValueError):
            co.assess_and_save(case["input"], "WEB-02", .35, finding_id="SIM-001", case_id=9999)
        self.assertTrue(op.load_assessments().empty)
        self.assertEqual(co.cases().iloc[0].status, "Na vyhodnotenie")

    def test_removed_finding_cannot_launch_an_incident(self):
        co.set_finding_status("SIM-001", "Odstránená", "Opravené oprávnenia exportu.")
        with self.assertRaises(ValueError):
            co.start_simulation("portal")
        self.assertEqual(co.finding("SIM-001")["status"], "Odstránená")
        self.assertTrue(co.events().detail.str.contains("SIM-001").any())

    def test_manual_inventory_and_findings_persist(self):
        asset_id = co.add_asset("Testovací server", "Servery", 1, "test.hrontech.internal", "Linux", "IT", "Stredná", "S - Web application")
        finding_id = co.add_finding(asset_id, "Testovacie zistenie", "Stredná", "Aktualizovať službu.", 500, "web")
        case = co.start_simulation("web", finding_id)
        self.assertEqual(case["asset_id"], asset_id)
        self.assertEqual(case["input"]["aktivum_variety"], ["S - Web application"])
        self.assertEqual(co.asset(asset_id)["owner"], "IT")

    def test_planning_does_not_multiply_scenario_risk_by_number_of_findings(self):
        register = co.risk_register()
        self.assertEqual(len(register), 7)
        self.assertEqual(register.typ.nunique(), 7)
        original = register.loc[register.typ == "portal", "riziko (€)"].iloc[0]
        co.add_finding("WEB-02", "Ďalšie zistenie", "Stredná", "Opraviť.", 500, "portal")
        updated = co.risk_register()
        self.assertEqual(updated.loc[updated.typ == "portal", "riziko (€)"].iloc[0], original)

    def test_delete_assessment_cascades_metadata(self):
        case = co.start_simulation("portal")
        record_id, _ = co.assess_and_save(case["input"], "WEB-02", .35, finding_id="SIM-001", case_id=case["id"])
        op.delete_assessments([record_id])
        with co.db() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM company_assessments").fetchone()[0], 0)

    def test_upstream_generator_payload_works_with_company_api(self):
        import api
        import simulacia

        case = co.start_simulation("portal")
        payload = simulacia.incident_body(case)
        self.assertNotIn("skutocny_dopad", payload)
        result = api.hodnotenie(api.Request(**payload))
        saved = co.assessments().iloc[0]
        self.assertEqual(saved.zdroj, "simulácia")
        self.assertTrue(pd.isna(saved.skutocny_dopad))
        self.assertEqual(result["asset_id"], "WEB-02")
        self.assertEqual(saved.case_id, case["id"])

    def test_known_impact_metadata_does_not_change_prediction(self):
        import api
        import simulacia

        case = co.start_simulation("portal")
        payload = simulacia.incident_body(case)
        first = api.hodnotenie(api.Request(**payload))
        second = api.hodnotenie(api.Request(**payload, skutocny_dopad="nízky"))
        self.assertEqual(first["pravdepodobnosti"], second["pravdepodobnosti"])

    def test_budget_includes_baseline_monitoring_and_never_overspends(self):
        register = co.risk_register()
        baseline = len(register) * op.MONITORING_COST * co.profile()["cost_factor"]
        self.assertFalse(co.budget_plan(baseline - 1, register)["affordable"])
        for budget in [baseline, baseline + 5000, 45000, 100000]:
            plan = co.budget_plan(budget, register)
            self.assertTrue(plan["affordable"])
            self.assertLessEqual(plan["spent"], budget)
            self.assertAlmostEqual(plan["spent"], baseline + (plan["selected"]["navýšenie (€)"].sum() if not plan["selected"].empty else 0))


if __name__ == "__main__":
    unittest.main()
