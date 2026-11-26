"""Visual shell and page structure for the incident assessment workspace."""

from pathlib import Path

import streamlit as st

PAGES = {
    "Firma": ("Firma HronTech", "Inventár, weby a bezpečnostné zistenia simulovanej výrobnej firmy.", "Firma"),
    "Simulácia": ("Simulácia incidentov", "Vyberte pripravenú situáciu a prejdite od firemnej zraniteľnosti k hodnoteniu a opatreniu.", "Simulácia"),
    "Živé sledovanie": ("Živé sledovanie firmy", "Priebežne prijaté modelové incidenty HronTech a ich vyhodnotenia.", "Živé sledovanie"),
    "Nové hodnotenie": (
        "Nové hodnotenie incidentu",
        "Zadajte údaje o incidente. Systém odhadne rozsah úniku dát a porovná ochranné opatrenia.",
        "Hodnotenie incidentu",
    ),
    "Uložené hodnotenia": (
        "Uložené hodnotenia",
        "Vyhľadávanie, porovnanie a export uložených hodnotení.",
        "História hodnotení",
    ),
    "Prehľad": (
        "Prehľad hodnotení",
        "Grafy dopadu, odporúčaných opatrení a vzorov útokov z uložených hodnotení.",
        "Analytický prehľad",
    ),
    "Register rizík": (
        "Register rizík",
        "Rizikové scenáre firmy HronTech, odporúčané opatrenia a plánovanie jej rozpočtu.",
        "Plánovanie ochrany",
    ),
    "Predpoklady": (
        "Predpoklady výpočtu",
        "Hodnoty a pravidlá použité pri výpočte rizika a výbere opatrení.",
        "Metodika a predpoklady",
    ),
}


def apply_style():
    stylesheet = Path(__file__).parent / "static" / "interface.css"
    st.html(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>")


def shell():
    # Keep form widgets when navigating to pages where they are not rendered.
    for key in list(st.session_state):
        if key.startswith(("f_", "company_")) or key in {"frekvencia", "rozpocet", "register_view", "history_search", "history_impact", "intake_step"}:
            st.session_state[key] = st.session_state[key]

    with st.sidebar:
        st.html(
            '<div class="atlas-brand"><span class="atlas-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>'
            '<div>safetyfirst<span>HronTech Strojárne</span></div></div>'
        )
        page = st.radio("Pracovný priestor", list(PAGES), key="workspace_page", label_visibility="collapsed")
        st.html(
            '<div class="atlas-sidebar-note"><span class="atlas-note-symbol">?</span>'
            '<strong>Odhad dopadu</strong><p>Rozsah úniku dát podľa charakteristík incidentu. '
            'Odporúčanie porovnáva cenu ochrany a očakávanú stratu.</p></div>'
            '<div class="atlas-sidebar-source"><span class="atlas-source-dot"></span>'
            'Simulované prostredie firmy<br><small>Model dopadu: historické incidenty VCDB</small></div>'
        )
    title, description, breadcrumb = PAGES[page]
    if page == "Nové hodnotenie" and "vysledok" in st.session_state:
        title = "Výsledok hodnotenia"
        description = "Odhad dopadu a odporúčané opatrenie pre zadaný incident. Hodnotenie je uložené v histórii."
    st.html(
        f'<header class="atlas-page-header"><h1>{title}</h1><p>{description}</p></header>'
    )
    return page


def footer():
    st.html(
        '<footer class="atlas-footer"><span>safetyfirst</span>'
        '<span>Predikcia dopadu a odporúčanie opatrení</span></footer>'
    )
