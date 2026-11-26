"""Overenie spoločného servera a databázového rozhrania pred nasadením."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

import opatrenia as op
import firma as co
import simulacia
from azure_app import app

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "test.db"
    sample = op.random_test_incident(67)
    result = op.assess(sample["vstup"])
    record_id = op.save_assessment(sample["vstup"], result, "API", name="Overenie nasadenia", path=path)
    rows = op.load_assessments(path=path)
    assert rows.iloc[0]["id"] == record_id
    assert rows.iloc[0]["vstup"]
    assert op.delete_assessments([record_id], path=path) == 1
    assert op.load_assessments(path=path).empty
    print("SQLite: zapis, citanie, mazanie OK")
    op.DB_PATH = path
    with TestClient(app) as client:
        for url in ["/", "/_stcore/health", "/api/moznosti", "/api/register", "/api/hodnotenia", "/api/firma", "/api/firma/aktiva", "/api/firma/zranitelnosti", "/api/firma/incidenty", "/api/firma/scenare", "/docs"]:
            response = client.get(url)
            assert response.status_code == 200, (url, response.status_code, response.text[:100])
            print(url, response.status_code)
        case = co.start_simulation("portal")
        response = client.post("/api/hodnotenie", json={**simulacia.incident_body(case), "nazov": "ASGI test"})
        assert response.status_code == 201, response.text
        assert client.get("/api/hodnotenia").json()[0]["nazov"] == "ASGI test"
        print("API: predikcia, zapis a citanie OK")
