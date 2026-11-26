"""Streamlit a existujúce REST API v jednom procese Azure App Service."""

import json
from pathlib import Path

import streamlit as st

from hrontech.api import app


@app.get("/health", include_in_schema=False)
def deployment_health():
    metadata = Path(__file__).resolve().parents[1] / "deployment.json"
    revision = json.loads(metadata.read_text(encoding="utf-8"))["revision"] if metadata.exists() else "local"
    return {"status": "ok", "revision": revision}


dashboard = st.App(str(Path(__file__).parent / "ui" / "app.py"))
app.router.lifespan_context = dashboard.lifespan()
app.mount("/", dashboard)
