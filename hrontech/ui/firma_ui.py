"""Company inventory, findings, simulation, and planning screens."""

import html
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from hrontech import firma as co
from hrontech import opatrenia as op
from hrontech import preklady as pr


def esc(value):
    return html.escape(str(value))


def euro(value):
    return f"{value:,.0f} €".replace(",", " ")


def company_page(start_scenario, start_manual):
    profile = co.profile()
    inventory, findings = co.assets(), co.findings()
    active = findings[findings.status != "Odstránená"]
    st.caption(f"{profile['location']} · {profile['employees']} zamestnancov")
    columns = st.columns(4)
    columns[0].metric("Skupiny aktív", len(inventory))
    columns[1].metric("Otvorené zraniteľnosti", len(active))
    columns[2].metric("Kritické zistenia", int((active.severity == "Kritická").sum()))
    columns[3].metric("Ročný rozpočet ochrany", euro(profile["budget"]))
    view = st.segmented_control("Zobrazenie firmy", ["Aktíva a weby", "Zraniteľnosti"],
                                key="company_view", default="Aktíva a weby" if "company_view" not in st.session_state else None,
                                width="stretch", label_visibility="collapsed")
    if view == "Zraniteľnosti":
        findings_page(start_scenario)
    elif view == "Nastavenie firmy":
        settings_page()
    else:
        assets_page(start_scenario, start_manual)


def assets_page(start_scenario, start_manual):
    inventory, findings = co.assets(), co.findings()
    heading, action = st.columns([4, 1])
    heading.subheader("Inventár")
    if action.button("Pridať aktívum", width="stretch"):
        add_asset_dialog()
    categories = st.pills("Kategórie aktív", sorted(inventory.category.unique()), selection_mode="multi", key="company_asset_categories")
    shown = inventory[inventory.category.isin(categories)].copy() if categories else inventory.copy()
    counts = findings[findings.status != "Odstránená"].groupby("asset_id").size()
    shown["open_findings"] = shown.id.map(counts).fillna(0).astype(int)
    st.dataframe(shown, hide_index=True, width="stretch", height=370,
                 column_order=["id", "name", "category", "quantity", "address", "criticality", "open_findings"],
                 column_config={"id": "ID", "name": "Aktívum", "category": "Kategória", "quantity": "Počet",
                                "address": "Adresa / označenie", "criticality": "Kritickosť", "open_findings": "Otvorené zistenia"})
    if shown.empty:
        return
    chosen = st.selectbox("Detail aktíva", shown.id.tolist(), format_func=lambda value: f"{value} · {co.asset(value)['name']}", key="company_asset_detail")
    a = co.asset(chosen)
    related = findings[findings.asset_id == chosen]
    st.html(f'<div class="company-asset-detail"><div><span>Technológia</span><strong>{esc(a["technology"])}</strong></div>'
            f'<div><span>Zodpovednosť</span><strong>{esc(a["owner"])}</strong></div>'
            f'<div><span>Adresa / označenie</span><strong>{esc(a["address"])}</strong></div></div>')
    if not related.empty:
        st.dataframe(related, hide_index=True, width="stretch", column_order=["id", "title", "severity", "status"],
                     column_config={"id": "Zistenie", "title": "Zraniteľnosť", "severity": "Závažnosť", "status": "Stav"})
    else:
        st.caption("Bez zistení.")
    st.button("Vyhodnotiť incident na tomto aktíve", on_click=start_manual, args=(chosen,), key="action_company_manual_asset")


def findings_page(start_scenario):
    findings = co.findings()
    heading, action = st.columns([4, 1])
    heading.subheader("Zraniteľnosti")
    if action.button("Pridať zraniteľnosť", width="stretch"):
        add_finding_dialog()
    left, right = st.columns(2)
    status = left.multiselect("Stav zistenia", co.STATUSES, key="company_status_filter")
    severity = right.multiselect("Závažnosť", co.SEVERITIES, key="company_severity_filter")
    shown = findings.copy()
    if status:
        shown = shown[shown.status.isin(status)]
    if severity:
        shown = shown[shown.severity.isin(severity)]
    st.dataframe(shown, hide_index=True, width="stretch", height=370,
                 column_order=["id", "asset_name", "title", "severity", "status", "cost"],
                 column_config={"id": "ID", "asset_name": "Aktívum", "title": "Zraniteľnosť", "severity": "Závažnosť",
                                "status": "Stav", "cost": st.column_config.NumberColumn("Odhad opravy (€)", format="%.0f")})
    if not shown.empty:
        selected = st.selectbox("Detail zraniteľnosti", shown.id.tolist(), key="company_finding_detail",
                                format_func=lambda value: f"{value} · {co.finding(value)['title']}")
        f = co.finding(selected)
        st.html(f'<div class="company-finding"><span class="company-severity">{esc(f["severity"])}</span>'
                f'<h3>{esc(f["title"])}</h3><p><b>Návrh opravy:</b> {esc(f["remediation"])}</p>'
                f'<p>Odhad jednorazovej opravy: <b>{euro(f["cost"])}</b>. Ide o evidenčný odhad, nie o ročnú cenu balíka ochrany.</p></div>')
        with st.form(f"company_update_{selected}"):
            status_key, note_key = f"company_status_editor_{selected}", f"company_note_editor_{selected}"
            new_status = st.selectbox("Nový stav", co.STATUSES, index=co.STATUSES.index(f["status"]) if status_key not in st.session_state else None, key=status_key)
            note = st.text_area("Poznámka k riešeniu", value=f["note"] if note_key not in st.session_state else None, max_chars=2000, key=note_key)
            if st.form_submit_button("Uložiť stav", type="primary"):
                co.set_finding_status(selected, new_status, note)
                st.rerun()
        st.button("Nasimulovať incident z tejto zraniteľnosti",
                  on_click=start_scenario, args=(f["scenario"], f["id"]), disabled=f["status"] == "Odstránená",
                  key="action_company_simulate_finding")


def settings_page():
    p = co.profile()
    st.subheader("Rozpočet a ekonomické predpoklady firmy")
    st.caption("Platí pre nové hodnotenia.")
    with st.form("company_settings"):
        budget = st.number_input("Ročný rozpočet na ochranu (€)", min_value=0., max_value=10_000_000., value=float(p["budget"]), step=1000.)
        columns = st.columns(3)
        losses = [columns[i].number_input(f"Strata pri dopade: {label} (€)", min_value=1., value=float(p["losses"][i]), step=1000.) for i, label in enumerate(op.LABELS)]
        cost_factor = st.number_input("Koeficient cien opatrení oproti základnému modelu", min_value=.01, max_value=10., value=float(p["cost_factor"]), step=.05,
                                      help="Pri 0,35 stoja opatrenia aj monitorovanie 35 % základnej modelovej ceny. Ide o predpoklad pre menšiu firmu.")
        horizon = st.number_input("Horizont ochrany (roky)", min_value=1, max_value=10, value=p["horizon"])
        if st.form_submit_button("Uložiť nastavenie firmy", type="primary"):
            try:
                co.update_settings(budget, losses, cost_factor, horizon)
                st.success("Nastavenie firmy bolo uložené.")
            except ValueError as error:
                st.error(str(error))

    with st.expander("Metodika výpočtu"):
        assumptions_page()


def simulation_page(start_scenario):
    findings = co.findings()
    scenario_id = st.selectbox("Scenár incidentu", list(co.SCENARIOS),
                               format_func=lambda value: co.SCENARIOS[value]["title"], key="company_scenario")
    scenario = co.SCENARIOS[scenario_id]
    descriptions = {
        "portal": "Neoprávnený export zákaziek zo zákazníckeho portálu.",
        "web": "Zmena obsahu verejného webu cez neaktualizovaný doplnok.",
        "vpn": "Prihlásenie do firemnej VPN získaným heslom.",
        "ransomware": "Zašifrovanie pracovných súborov a záloh.",
        "phishing": "Získanie prístupu k firemnej pošte.",
        "export": "Odoslanie interného exportu nesprávnemu príjemcovi.",
        "loss": "Strata notebooku s nešifrovaným diskom.",
    }
    st.write(descriptions[scenario_id])
    candidates = findings[(findings.scenario == scenario_id) & (findings.status != "Odstránená")]
    if candidates.empty:
        st.caption("Všetky súvisiace zistenia sú odstránené.")
    else:
        finding_id = st.selectbox("Súvisiaca zraniteľnosť", candidates.id.tolist(),
            format_func=lambda value: f"{value} – {candidates.loc[candidates.id == value, 'title'].iloc[0]}",
            key=f"company_scenario_finding_{scenario_id}")
        st.button("Vytvoriť incident", type="primary", on_click=start_scenario, args=(scenario_id, finding_id))
    st.divider()
    st.subheader("Posledné incidenty")
    cases = co.cases()
    if cases.empty:
        st.caption("Zatiaľ žiadne incidenty.")
    else:
        st.dataframe(cases, hide_index=True, width="stretch", column_order=["id", "title", "asset_name", "finding_id", "status", "created_at"],
                     column_config={"id": "Incident", "title": "Scenár", "asset_name": "Aktívum", "finding_id": "Zistenie", "status": "Stav", "created_at": "Vytvorené"})
    with st.expander("Denník zmien"):
        st.dataframe(co.events(), hide_index=True, width="stretch", column_order=["created_at", "kind", "detail"],
                     column_config={"created_at": "Čas", "kind": "Typ", "detail": "Záznam"})


@st.fragment(run_every=2)
def live_page():
    """Upstream live-monitoring feature, scoped to company-linked assessments."""
    source = st.segmented_control("Zdroje hodnotení", ["Všetky hodnotenia", "Zo simulácie"], default="Všetky hodnotenia",
                                  key="company_live_scope", width="stretch")
    records = co.assessments()
    shown = records if source == "Všetky hodnotenia" else records[records.zdroj == "simulácia"]
    if shown.empty:
        st.caption("Zatiaľ žiadne hodnotenia z tohto zdroja.")
        return
    times = pd.to_datetime(shown.vytvorene, errors="coerce")
    seconds = max(0, int((datetime.now() - times.max()).total_seconds()))
    columns = st.columns(3)
    columns[0].metric("Prijaté hodnotenia", len(shown))
    columns[1].metric("Predikovaný vysoký dopad", int((shown.predikovany_dopad == "vysoký").sum()))
    columns[2].metric("Posledné hodnotenie pred", f"{seconds} s" if seconds < 120 else f"{seconds // 60} min")
    st.subheader("Posledné prijaté incidenty")
    latest = shown.sort_values("id", ascending=False).head(12)
    st.dataframe(latest, hide_index=True, width="stretch", column_order=["vytvorene", "asset_name", "finding_id", "nazov", "predikovany_dopad", "ocakavana_strata", "opatrenie", "zdroj"],
                 column_config={"vytvorene": "Čas", "asset_name": "Aktívum", "finding_id": "Zistenie", "nazov": "Incident", "predikovany_dopad": "Odhad dopadu",
                                "ocakavana_strata": st.column_config.NumberColumn("Ročný modelový odhad (€)", format="%.0f"), "opatrenie": "Opatrenie", "zdroj": "Zdroj"})
    frame = shown.sort_values("id").tail(60).copy()
    frame["čas"] = pd.to_datetime(frame.vytvorene)
    chart = alt.Chart(frame).mark_circle(size=100).encode(
        x=alt.X("čas:T", title="Čas prijatia", axis=alt.Axis(format="%H:%M:%S")),
        y=alt.Y("ocakavana_strata:Q", title="Ročný modelový odhad straty (€)"),
        color=alt.Color("predikovany_dopad:N", title="Odhad dopadu", scale=alt.Scale(domain=op.LABELS, range=["#287a62", "#b87926", "#be514a"])),
        tooltip=["asset_name", "nazov", "predikovany_dopad", "ocakavana_strata", "opatrenie"]
    ).properties(height=280).configure_view(stroke=None)
    st.altair_chart(chart, width="stretch")


def planning_page():
    profile = co.profile()
    register = co.risk_register()
    if register.empty:
        st.success("V evidencii nie sú otvorené zistenia pre pripravené scenáre. To neznamená nulové riziko firmy.")
        return
    st.dataframe(register, hide_index=True, width="stretch", column_order=["scenár", "otvorené zistenia", "frekvencia", "dopad", "riziko (€)", "opatrenie", "cena (€)", "prínos (€)", "CIS"],
                 column_config={c: st.column_config.NumberColumn(c, format="%.0f") for c in ["riziko (€)", "cena (€)", "prínos (€)"]})
    chart = alt.Chart(register).mark_bar(color="#087f8c", cornerRadiusEnd=4).encode(
        y=alt.Y("scenár:N", sort="-x", title=None, axis=alt.Axis(labelLimit=310)),
        x=alt.X("riziko (€):Q", title="Očakávaná ročná strata (€)"),
        tooltip=["scenár", "opatrenie", "riziko (€)", "cena (€)"]
    ).properties(height=300).configure_view(stroke=None)
    st.altair_chart(chart, width="stretch")
    st.subheader("Výber opatrení v rozpočte")
    budget = st.number_input("Dostupný ročný rozpočet (€)", min_value=0., max_value=10_000_000., value=float(profile["budget"]), step=1000., key="company_planning_budget")
    plan = co.budget_plan(budget, register)
    if not plan["affordable"]:
        st.warning(f"Samotné monitorovanie všetkých evidovaných scenárov stojí {euro(plan['baseline'])} ročne. Tento rozpočet nestačí na základné pokrytie.")
        return
    selected, remaining = plan["selected"], plan["remaining"]
    columns = st.columns(3)
    columns[0].metric("Vybrané scenáre", len(selected))
    columns[1].metric("Celkové ročné náklady", euro(plan["spent"]))
    columns[2].metric("Zostávajúci rozpočet", euro(remaining))
    if not selected.empty:
        st.dataframe(selected, hide_index=True, width="stretch", column_order=["scenár", "opatrenie", "cena (€)", "navýšenie (€)", "prínos (€)", "CIS"])
    else:
        st.info("Do tohto rozpočtu sa nezmestí žiadne z ekonomicky prínosných odporúčaní.")
    st.caption(f"Celková cena zahŕňa {euro(plan['baseline'])} monitorovania všetkých scenárov. Vybraná ochrana ho nahrádza; navýšenie je rozdiel oproti monitorovaniu. Poradie je podľa čistého prínosu na euro, nie presné kombinatorické optimum. Zdieľané opatrenia sa cenovo nezlučujú.")


def assumptions_page():
    p = co.profile()
    st.write("Ukážková firma a finančné predpoklady slúžia na simuláciu. Model používa historické incidenty VCDB.")
    st.subheader("Čo sa predikuje")
    st.write("Model odhaduje rozsah úniku dát: nízky pod 1 000 záznamov, stredný od 1 000 do 99 999 a vysoký od 100 000. Neodhaduje pravdepodobnosť zneužitia zraniteľnosti, odstávku CNC ani fyzickú bezpečnosť výroby.")
    st.subheader("Predpoklady HronTech")
    st.dataframe(pd.DataFrame({"Dopad": op.LABELS, "Modelová strata (€)": p["losses"]}), hide_index=True, width="stretch")
    st.write(f"Horizont ochrany: {p['horizon']} roky. Ceny opatrení a monitorovania: {p['cost_factor']:.0%} základného modelu. Ročný rozpočet: {euro(p['budget'])}.")
    options = op.OPTIONS.copy()
    st.dataframe(options, width="stretch")
    st.caption("Účinnosť prevencie (40 %) a detekcie a reakcie (35 %) sú predpoklady. Opatrenia začnú pôsobiť až po zavedení. Výber minimalizuje cenu ochrany plus zostávajúcu očakávanú stratu.")
    st.code("očakávaná ročná strata = frekvencia × Σ P(dopad) × modelová strata(dopad)\ncelkové náklady = ročná cena ochrany + zostávajúca očakávaná strata", language=None)
    st.caption("Profil výroby a malej organizácie vstupuje do modelu. Slovensko sa mapuje na kategóriu ostatných krajín. Samotné počty počítačov neovplyvňujú ML predikciu. Jednorazová cena opravy zraniteľnosti je evidenčný odhad, oddelený od ročných balíkov CIS.")


@st.dialog("Nové aktívum", width="large")
def add_asset_dialog():
    inventory = co.assets()
    with st.form("company_add_asset"):
        name = st.text_input("Názov aktíva")
        left, right = st.columns(2)
        category = left.selectbox("Kategória", sorted(inventory.category.unique()))
        quantity = right.number_input("Počet kusov / účtov", min_value=1, max_value=10000, value=1)
        left, right = st.columns(2)
        address = left.text_input("Adresa alebo označenie")
        technology = right.text_input("Technológia")
        owner = left.text_input("Zodpovedná osoba alebo oddelenie")
        criticality = right.selectbox("Kritickosť aktíva", co.SEVERITIES)
        model_asset = st.selectbox("Typ zariadenia alebo služby", op.choices()["aktivum_variety"], format_func=pr.formatter("aktivum_variety"))
        if st.form_submit_button("Uložiť aktívum", type="primary"):
            try:
                co.add_asset(name, category, quantity, address, technology, owner, criticality, model_asset)
                st.rerun()
            except ValueError as error:
                st.error(str(error))

@st.dialog("Nová zraniteľnosť", width="large")
def add_finding_dialog():
    inventory = co.assets()
    with st.form("company_add_finding"):
        asset_id = st.selectbox("Dotknuté aktívum", inventory.id.tolist(), format_func=lambda value: f"{value} · {co.asset(value)['name']}")
        title = st.text_input("Popis zraniteľnosti", max_chars=200)
        severity = st.selectbox("Závažnosť zistenia", co.SEVERITIES)
        remediation = st.text_area("Navrhnutá oprava", max_chars=2000)
        cost = st.number_input("Jednorazový odhad opravy (€)", min_value=0, max_value=1000000, value=1000)
        scenario = st.selectbox("Súvisiaci scenár", list(co.SCENARIOS), format_func=lambda value: co.SCENARIOS[value]["title"])
        if st.form_submit_button("Uložiť zraniteľnosť", type="primary"):
            try:
                co.add_finding(asset_id, title, severity, remediation, cost, scenario)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
