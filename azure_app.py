"""Streamlit a existujúce REST API v jednom procese Azure App Service."""

import streamlit as st

from api import app

dashboard = st.App("app.py")
app.router.lifespan_context = dashboard.lifespan()
app.mount("/", dashboard)
