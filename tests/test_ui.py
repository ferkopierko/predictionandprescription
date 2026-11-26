import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from hrontech import firma, opatrenia


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = patch.object(opatrenia, "DB_PATH", Path(self.directory.name) / "ui.db")
        self.database.start()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "hrontech/ui/app.py")).run(timeout=60)

    def tearDown(self):
        self.database.stop()
        self.directory.cleanup()

    def assert_page_ok(self):
        self.assertFalse(self.app.exception, [str(error) for error in self.app.exception])

    def button(self, label):
        return next(button for button in self.app.button if button.label == label)

    def test_navigation_and_subviews(self):
        for section in ["Firma", "Incidenty", "Hodnotenia", "Prehľad", "Ochrana", "Nastavenia"]:
            self.app.radio(key="main_nav").set_value(section).run(timeout=60)
            self.assert_page_ok()
        self.app.radio(key="main_nav").set_value("Incidenty").run(timeout=60)
        self.app.segmented_control(key="view_Incidenty").set_value("Živé sledovanie").run(timeout=60)
        self.assert_page_ok()
        self.app.radio(key="main_nav").set_value("Hodnotenia").run(timeout=60)
        self.app.segmented_control(key="view_Hodnotenia").set_value("Nové hodnotenie").run(timeout=60)
        self.assert_page_ok()

    def test_scenario_opens_assessment_and_saves_result(self):
        self.app.radio(key="main_nav").set_value("Incidenty").run(timeout=60)
        self.assertFalse(self.app.info)
        self.button("Vytvoriť incident").click().run(timeout=60)
        self.assert_page_ok()
        self.assertEqual(self.app.session_state["workspace_page"], "Nové hodnotenie")
        self.assertEqual(self.app.radio(key="main_nav").value, "Hodnotenia")
        self.button("Pokračovať k vyhodnoteniu").click().run(timeout=60)
        self.button("Vyhodnotiť a uložiť").click().run(timeout=60)
        self.assert_page_ok()
        self.assertEqual(len(firma.assessments()), 1)
        self.assertTrue(any("Hodnotenie uložené" in item.value for item in self.app.success))

    def test_creation_form_opens_in_dialog(self):
        self.button("Pridať aktívum").click().run(timeout=60)
        self.assert_page_ok()
        self.assertTrue(any(item.label == "Názov aktíva" for item in self.app.text_input))


if __name__ == "__main__":
    unittest.main()
