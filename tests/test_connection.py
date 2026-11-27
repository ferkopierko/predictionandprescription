"""Serverless SQL can reject the initial connection while waking up."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hrontech import opatrenia as op


class ConnectionTests(unittest.TestCase):
    def driver(self, outcomes):
        return SimpleNamespace(OperationalError=RuntimeError, connect=Mock(side_effect=outcomes))

    def run_connect(self, driver):
        with patch.dict(op.os.environ, AZURE_SQL_CONNECTION_STRING="test"), \
             patch.object(op, "azure_sql_driver", return_value=driver), \
             patch.object(op.time, "sleep") as sleep:
            result = op.connect()
        return result, sleep

    def test_resume_failure_then_success(self):
        connection = object()
        driver = self.driver([
            RuntimeError("Database 'demo' is not currently available. Please retry later."),
            RuntimeError("40613"), connection,
        ])
        result, sleep = self.run_connect(driver)
        self.assertIs(result, connection)
        self.assertEqual(driver.connect.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 10])

    def test_authentication_failure_is_not_retried(self):
        driver = self.driver([RuntimeError("Login failed for user (18456)")])
        with self.assertRaisesRegex(RuntimeError, "18456"):
            self.run_connect(driver)
        self.assertEqual(driver.connect.call_count, 1)

    def test_unavailable_database_has_bounded_attempts(self):
        driver = self.driver([RuntimeError("40613")] * 6)
        with self.assertRaisesRegex(RuntimeError, "40613"):
            self.run_connect(driver)
        self.assertEqual(driver.connect.call_count, 6)

    def test_resume_deadline_stops_retries(self):
        driver = self.driver([RuntimeError("40613")])
        with patch.object(op.time, "monotonic", side_effect=[0, 0, 121]):
            with self.assertRaisesRegex(RuntimeError, "40613"):
                self.run_connect(driver)
        self.assertEqual(driver.connect.call_count, 1)
