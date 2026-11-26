"""Company inventory, findings, simulation, and planning screens."""

import html
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import firma as co
import opatrenia as op
import preklady as pr


def esc(value):
    return html.escape(str(value))


def euro(value):
    return f"{value:,.0f} €".replace(",", " ")


def company_page(start_scenario, start_manual):
    profile = co.profile()
    inventory, findings = co.assets(), co.findings()
    active = findings[findings.status != "Odstránená"]
    st.html(
        '<section class="company-header"><div class="company-factory" aria-hidden="true">'
        '<span></span><i></i><i></i><i></i></div><div>'
        '<span class="company-simulation">Simulovaná výrobná firma</span>'
        f'<h2>{esc(profile["name"])}</h2><p>{esc(profile["description"])}</p>'
        f'<small>{esc(profile["location"])} · {profile["employees"]} zamestnancov</small></div></section>'
    )
    columns = st.columns(4)
    columns[0].metric("Skupiny aktív", len(inventory))
    columns[1].metric("Otvorené zraniteľnosti", len(active))
    columns[2].metric("Kritické zistenia", int((active.severity == "Kritická").sum()))
    columns[3].metric("Ročný rozpočet ochrany", euro(profile["budget"]))
    view = st.segmented_control("Zobrazenie firmy", ["Aktíva a weby", "Zraniteľnosti", "Nastavenie firmy"],
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
    st.subheader("Inventár firmy")
    st.caption("Skupina počítačov má uvedený počet kusov. Weby a adresy patria k fiktívnemu prostrediu; nič sa neskenuje.")
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
        st.info("Pri tomto aktíve zatiaľ nie sú zaevidované zraniteľnosti.")
    st.button("Vyhodnotiť incident na tomto aktíve", icon=":material/analytics:", on_click=start_manual, args=(chosen,), key="action_company_manual_asset")
    with st.expander("Pridať aktívum do inventára", icon=":material/add:"):
        with st.form("company_add_asset"):
            name = st.text_input("Názov aktíva")
            left, right = st.columns(2)
            category = left.selectbox("Kategória", sorted(inventory.category.unique()))
            quantity = right.number_input("Počet kusov / účtov", min_value=1, max_value=10000, value=1)
            address = st.text_input("Adresa alebo označenie")
            technology = st.text_input("Technológia")
            owner = st.text_input("Zodpovedná osoba alebo oddelenie")
            criticality = st.selectbox("Kritickosť aktíva", co.SEVERITIES)
            model_asset = st.selectbox("Typ zariadenia alebo služby", op.choices()["aktivum_variety"], format_func=pr.formatter("aktivum_variety"))
            if st.form_submit_button("Uložiť aktívum", type="primary"):
                try:
                    co.add_asset(name, category, quantity, address, technology, owner, criticality, model_asset)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def findings_page(start_scenario):
    findings = co.findings()
    st.subheader("Evidencia zraniteľností")
    st.caption("SIM označuje modelové bezpečnostné zistenie. Závažnosť zistenia je samostatná od predikovaného rozsahu úniku dát.")
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
        st.button("Nasimulovať incident z tejto zraniteľnosti", icon=":material/science:",
                  on_click=start_scenario, args=(f["scenario"], f["id"]), disabled=f["status"] == "Odstránená",
                  key="action_company_simulate_finding")
    with st.expander("Pridať zraniteľnosť", icon=":material/add:"):
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


def settings_page():
    p = co.profile()
    st.subheader("Rozpočet a ekonomické predpoklady firmy")
    st.caption("Tieto hodnoty vstupujú do každého nového hodnotenia. Staršie hodnotenia si uchovávajú vlastnú kópiu predpokladov.")
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


def simulation_page(start_scenario):
    st.info("Simulácia vytvorí evidovaný incident a predvyplní hodnotenie. Nespúšťa útok ani skenovanie siete.", icon=":material/science:")
    findings = co.findings()
    for scenario_id, scenario in co.SCENARIOS.items():
        candidates = findings[(findings.scenario == scenario_id) & (findings.status != "Odstránená")]
        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"**{scenario['title']}**")
            left.write(scenario["description"])
            left.caption(f"Modelová frekvencia: {scenario['frequency']:g} za rok · {len(candidates)} nevyriešených zistení")
            if not candidates.empty:
                finding_id = right.selectbox("Zdrojové zistenie", candidates.id.tolist(), key=f"company_scenario_finding_{scenario_id}")
                right.button("Nasimulovať", icon=":material/play_arrow:", key=f"action_company_start_{scenario_id}", type="primary",
                              on_click=start_scenario, args=(scenario_id, finding_id))
            else:
                right.caption("Všetky súvisiace zistenia sú odstránené.")
    st.subheader("Evidované simulované incidenty")
    cases = co.cases()
    if cases.empty:
        st.caption("Zatiaľ nebola spustená žiadna simulácia.")
    else:
        st.dataframe(cases, hide_index=True, width="stretch", column_order=["id", "title", "asset_name", "finding_id", "status", "created_at"],
                     column_config={"id": "Incident", "title": "Scenár", "asset_name": "Aktívum", "finding_id": "Zraniteľnosť", "status": "Stav", "created_at": "Vytvorené"})
    with st.expander("Denník zmien"):
        st.dataframe(co.events(), hide_index=True, width="stretch", column_order=["created_at", "kind", "detail"],
                     column_config={"created_at": "Čas", "kind": "Typ udalosti", "detail": "Záznam"})


@st.fragment(run_every=2)
def live_page():
    """Upstream live-monitoring feature, scoped to company-linked assessments."""
    source = st.segmented_control("Zdroje hodnotení", ["Generátor", "Všetky firemné hodnotenia"], default="Generátor",
                                  key="company_live_scope", width="stretch")
    records = co.assessments()
    shown = records if source == "Všetky firemné hodnotenia" else records[records.zdroj == "simulácia"]
    st.caption("Modelové incidenty, nie skutočná sieťová prevádzka. Obnovenie každé 2 sekundy. Predikcia nie je potvrdený rozsah úniku.")
    with st.expander("Spustiť generátor incidentov"):
        st.write("V termináli s aktivovaným prostredím spustite napríklad desať incidentov. Firma aj API musia byť spustené.")
        st.code("python simulacia.py --pocet 10 --interval 3 --seed 67", language="bash")
        st.caption("Docker: docker compose --profile simulacia up -d --build. Generátor zastavíte cez Ctrl+C alebo zastavením jeho kontajnera.")
    if shown.empty:
        st.info("Zatiaľ neprišlo žiadne hodnotenie z tohto zdroja. Spustite generátor alebo zobrazte všetky firemné hodnotenia.")
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
    st.caption("Jednotlivé riadky môžu opakovať ten istý scenár. Ich ročné straty preto nesčítavame ako celkové riziko firmy.")


def planning_page():
    profile = co.profile()
    register = co.risk_register()
    st.caption("Plánovanie je iba pre HronTech. Každá rodina incidentov je započítaná raz, aj keď má viac súvisiacich zraniteľností.")
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
    st.info("Firma, aktíva, zraniteľnosti, frekvencie a finančné hodnoty sú simulované. Klasifikátor je natrénovaný na skutočných historických incidentoch VCDB.")
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
