"""Lokálna aplikácia: pridanie zraniteľnosti, predikcia závažnosti a odporúčané opatrenie.

Spustenie: streamlit run app.py
"""

import json
import re

import altair as alt
import pandas as pd
import streamlit as st

import opatrenia as op
import prevadzka

st.set_page_config(page_title="Opatrenia pre zraniteľnosti", page_icon="🛡️", layout="wide")

EXAMPLES = {
    "Vlastný záznam": ("", "", []),
    "Vzdialené spustenie kódu bez prihlásenia": (
        "CVE-2026-90001",
        "A stack-based buffer overflow in the web management interface of Acme Router 3.2 allows "
        "unauthenticated remote attackers to execute arbitrary code via a crafted HTTP request.",
        ["CWE-787"],
    ),
    "Stored XSS pre prihlásených používateľov": (
        "CVE-2026-90002",
        "A stored cross-site scripting vulnerability in the comment module of Example CMS before 2.4 "
        "allows authenticated users to inject arbitrary web script via the title parameter.",
        ["CWE-79"],
    ),
    "Lokálne zvýšenie oprávnení": (
        "CVE-2026-90003",
        "Improper privilege management in the installer of Example Agent on Windows allows a local "
        "attacker to gain elevated privileges by replacing a temporary file.",
        ["CWE-269"],
    ),
}


def euro(value):
    return f"{value:,.0f} €".replace(",", " ")


def decimal(value, digits=2):
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def percent(value):
    return f"{value * 100:.1f} %".replace(".", ",")


def cwe_label(cwe):
    return f"{cwe}: {op.CWE_NAMES[cwe]}" if cwe in op.CWE_NAMES else cwe


@st.cache_resource(show_spinner="Pripravujem model. Pri prvom spustení ho treba naučiť, trvá to 1 až 3 minúty.", max_entries=1)
def get_bundle(_path_key, _modified):
    return op.load_active()


def active_bundle():
    """Načíta aktuálny model. Po pretrénovaní sa zmení dátum súboru a model sa obnoví."""
    path = op.active_model_path()
    return get_bundle(str(path), path.stat().st_mtime if path.exists() else 0)


@st.cache_data(show_spinner=False)
def get_test_results():
    return pd.read_csv(op.TEST_RESULTS_PATH, keep_default_na=False)


@st.cache_data(show_spinner=False)
def known_cwes(_bundle):
    known = op.known_cwe_ids(_bundle)
    common = [cwe for cwe in known if cwe in op.CWE_NAMES]
    return common + [cwe for cwe in known if cwe not in op.CWE_NAMES]


def apply_example():
    cve_id, description, cwe_ids = EXAMPLES[st.session_state["example"]]
    st.session_state["cve_id"] = cve_id
    st.session_state["description"] = description
    st.session_state["cwe_ids"] = cwe_ids


def probability_chart(probabilities):
    frame = pd.DataFrame({
        "závažnosť": op.LABELS,
        "pravdepodobnosť": [probabilities[label] for label in op.LABELS],
    })
    frame["text"] = frame["pravdepodobnosť"].map(percent)
    base = alt.Chart(frame).encode(
        y=alt.Y("závažnosť:N", sort=op.LABELS[::-1], title=None, axis=alt.Axis(ticks=False, domain=False)),
        x=alt.X("pravdepodobnosť:Q", title=None, axis=None, scale=alt.Scale(domain=[0, 1.15])),
        tooltip=[alt.Tooltip("závažnosť:N"), alt.Tooltip("text:N", title="pravdepodobnosť")],
    )
    bars = base.mark_bar(color="#2a78d6", cornerRadiusEnd=4, height=22)
    labels = base.mark_text(align="left", dx=5).encode(text="text:N")
    return (bars + labels).properties(height=170)


def show_result(result, title):
    st.subheader(title)
    for warning in result["warnings"]:
        st.warning(warning)

    action = result["action"]
    first, second, third = st.columns([1.5, 1, 1])
    first.metric("Odporúčané opatrenie", action)
    second.metric("Najpravdepodobnejšia závažnosť", result["predicted_class"])
    third.metric("Očakávaná denná škoda", f"{decimal(result['expected_risk'])} €")

    st.markdown(f"**Čo urobiť:** {result['steps']}")
    if action == "Dočasná ochrana":
        st.markdown(
            f"**Termíny:** ochrana do {result['protect_by']:%d.%m.%Y}, oprava do {result['fix_by']:%d.%m.%Y}."
        )
        st.markdown(f"**Vhodná dočasná ochrana:** {result['control']}.")
    else:
        st.markdown(f"**Termín opravy:** do {result['fix_by']:%d.%m.%Y}.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Pravdepodobnosť závažnosti**")
        st.altair_chart(probability_chart(result["probabilities"]), width="stretch")
    with right:
        st.markdown("**Porovnanie opatrení**")
        costs = result["costs"].copy()
        costs.insert(1, "odporúčané", costs["opatrenie"].eq(action).map({True: "áno", False: ""}))
        st.dataframe(
            costs,
            hide_index=True,
            width="stretch",
            column_config={
                "práca (€)": st.column_config.NumberColumn(format="%.0f"),
                "efektívne dni expozície": st.column_config.NumberColumn("dni expozície", format="%.1f"),
                "očakávaná škoda (€)": st.column_config.NumberColumn(format="%.0f"),
                "očakávané náklady spolu (€)": st.column_config.NumberColumn("spolu (€)", format="%.0f"),
            },
        )
    st.caption(
        "Sumy vychádzajú z predpokladov na záložke Predpoklady. Výsledok je prvotné triedenie "
        "a nenahrádza posúdenie analytikom."
    )


def new_record_tab(bundle):
    st.selectbox("Príklad na vyskúšanie", list(EXAMPLES), key="example", on_change=apply_example)

    with st.form("new_record"):
        st.text_input("CVE-ID (nepovinné)", key="cve_id", placeholder="CVE-2026-12345")
        st.text_area(
            "Popis zraniteľnosti (po anglicky)",
            key="description",
            height=130,
            help="Model bol naučený na anglických popisoch z databázy CVE.",
        )
        st.multiselect(
            "Typ slabiny CWE (nepovinné)",
            known_cwes(bundle),
            key="cwe_ids",
            format_func=cwe_label,
            placeholder="Vyberte typ, ak je známy",
        )
        submitted = st.form_submit_button("Pridať a predpovedať", type="primary")

    if submitted:
        cve_id = st.session_state["cve_id"].strip().upper()
        description = st.session_state["description"].strip()
        cwe_ids = st.session_state["cwe_ids"]
        existing = op.load_records()

        if not description:
            st.error("Vyplňte popis zraniteľnosti.")
        elif cve_id and not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve_id):
            st.error("CVE-ID musí mať tvar CVE-RRRR-ČÍSLO, napríklad CVE-2026-12345.")
        elif cve_id and cve_id in set(existing["cve_id"]):
            st.error(f"Záznam {cve_id} už existuje. Ak ho chcete zmeniť, najprv ho vymažte na záložke Pridané záznamy.")
        else:
            result = op.assess(bundle, description, cwe_ids)
            op.add_record(cve_id, description, cwe_ids, result)
            st.session_state["last_result"] = (cve_id or "Záznam bez CVE-ID", result)

    if "last_result" in st.session_state:
        name, result = st.session_state["last_result"]
        st.divider()
        show_result(result, f"Výsledok: {name}")


def records_tab():
    records = op.load_records()
    if records.empty:
        st.info("Zatiaľ nie sú pridané žiadne záznamy. Pridajte prvý na záložke Nový záznam.")
        return

    records = records.sort_values("ocakavane_denne_riziko", ascending=False).reset_index(drop=True)
    records.insert(0, "priorita", records.index + 1)
    st.caption("Záznamy sú zoradené podľa priority, teda od najvyššej očakávanej dennej škody.")

    st.dataframe(
        records.drop(columns="zaznam_id"),
        hide_index=True,
        width="stretch",
        column_order=[
            "priorita", "cve_id", "opatrenie", "ocakavane_denne_riziko",
            *[f"P_{label}" for label in op.LABELS],
            "cwe_text", "description", "pridane",
        ],
        column_config={
            "pridane": "pridané",
            "cve_id": "CVE-ID",
            "description": st.column_config.TextColumn("popis", width="medium"),
            "cwe_text": "CWE",
            "ocakavane_denne_riziko": st.column_config.NumberColumn("denná škoda (€)", format="%.2f"),
            **{f"P_{label}": st.column_config.NumberColumn(f"P({label})", format="%.2f") for label in op.LABELS},
        },
    )

    st.download_button(
        "Stiahnuť ako CSV",
        records.drop(columns="zaznam_id").to_csv(index=False).encode("utf-8-sig"),
        file_name="pridane_zaznamy.csv",
        mime="text/csv",
    )

    labels = {
        row.zaznam_id: f"{row.priorita}. {row.cve_id or 'bez CVE-ID'}: {row.description[:60]}"
        for row in records.itertuples()
    }
    with st.form("delete_records"):
        to_delete = st.multiselect("Vymazať záznamy", list(labels), format_func=labels.get, placeholder="Vyberte záznamy")
        if st.form_submit_button("Vymazať vybrané") and to_delete:
            op.delete_records(to_delete)
            st.rerun()


def overview_tab():
    if not op.TEST_RESULTS_PATH.exists():
        st.info("Výsledky zatiaľ neexistujú. Spustite notebook preskriptivna_udrzba.ipynb.")
        return

    results = get_test_results()
    st.caption("Zraniteľnosti z rokov 2020 a 2021, na ktorých bol postup vyhodnotený v notebooku.")

    columns = st.columns(len(op.ACTION_NAMES))
    for column, action in zip(columns, op.ACTION_NAMES):
        count = int((results["opatrenie"] == action).sum())
        column.metric(action, f"{count:,}".replace(",", " "), percent(count / len(results)), delta_color="off", delta_arrow="off")

    filter_action, filter_severity, search = st.columns(3)
    actions = filter_action.multiselect("Opatrenie", op.ACTION_NAMES, placeholder="Všetky")
    severities = filter_severity.multiselect("Skutočná závažnosť", op.LABELS, placeholder="Všetky")
    query = search.text_input("Hľadať CVE-ID alebo CWE", placeholder="CVE-2021-, CWE-79")

    shown = results
    if actions:
        shown = shown[shown["opatrenie"].isin(actions)]
    if severities:
        shown = shown[shown["severity_v3"].isin(severities)]
    if query.strip():
        needle = query.strip()
        shown = shown[
            shown["cve_id"].str.contains(needle, case=False, regex=False)
            | shown["cwe_text"].str.contains(needle, case=False, regex=False)
        ]

    st.markdown(f"Zobrazených záznamov: **{len(shown):,}**".replace(",", " "))
    st.dataframe(
        shown,
        hide_index=True,
        width="stretch",
        height=380,
        column_config={
            "cve_id": "CVE-ID",
            "year": st.column_config.NumberColumn("rok", format="%d"),
            "severity_v3": "skutočná závažnosť",
            "cwe_text": "CWE",
            "P_CRITICAL": st.column_config.NumberColumn("P(CRITICAL)", format="%.2f"),
            "ocakavane_denne_riziko": st.column_config.NumberColumn("denná škoda (€)", format="%.2f"),
        },
    )

    for name in ["9_porovnanie_strategii.png", "8_opatrenia_podla_zavaznosti.png", "7_prahy_opatreni.png"]:
        path = op.FIGURES_DIR / name
        if path.exists():
            st.image(str(path), width=900)


def utc_label(value):
    return f"{value.replace('T', ' ')[:16]} UTC" if value else "zatiaľ nie"


def show_model_report():
    if not op.PRODUCTION_REPORT_PATH.exists():
        return
    report = json.loads(op.PRODUCTION_REPORT_PATH.read_text(encoding="utf-8"))
    with st.expander(f"Prevádzkový model, naučený {report['natrenovane']}"):
        names = {
            "novy_model": "Nový model",
            "novy_model_iba_hodnotenie_nvd": "Nový model, iba hodnotenia NVD",
            "novy_model_iba_hodnotenie_cna": "Nový model, iba hodnotenia CNA",
            "povodny_model_do_2018": "Pôvodný model z notebooku",
        }
        rows = [{"model": label, **report[key]} for key, label in names.items() if key in report]
        table = pd.DataFrame(rows).drop(columns="opatrenia_podiel")
        st.caption(f"Vyhodnotenie na zraniteľnostiach zverejnených od {report['testovacie_obdobie_od']}.")
        st.dataframe(table.round(3), hide_index=True, width="stretch")


@st.fragment(run_every="20s")
def live_tab():
    status = prevadzka.read_status()
    if not status or "last_attempt" not in status:
        st.info("Prevádzka zatiaľ nebežala. Spustite ju príkazom docker compose up -d.")
        return

    records = prevadzka.read_records()
    last_success = status.get("last_success", "")
    interval = int(status.get("poll_seconds", prevadzka.POLL_SECONDS))
    silent = not last_success or (
        pd.Timestamp.now("UTC") - pd.Timestamp(last_success, tz="UTC")
    ).total_seconds() > 2 * interval + 300

    if status.get("last_error"):
        st.warning(f"Posledné načítanie z NVD zlyhalo, prevádzka to skúsi znova. {status['last_error']}")
    elif silent:
        st.warning("Prevádzka sa dlhšie neozvala. Skontrolujte kontajner príkazom docker compose logs worker.")

    published = pd.to_datetime(records["published"], utc=True) if len(records) else pd.Series(dtype="datetime64[ns, UTC]")
    last_day = int((published >= pd.Timestamp.now("UTC") - pd.Timedelta(hours=24)).sum())
    first, second, third = st.columns(3)
    first.metric("Posledné úspešné načítanie", utc_label(last_success))
    second.metric("Zverejnené za 24 hodín", f"{last_day:,}".replace(",", " "))
    third.metric("Spracované spolu", f"{len(records):,}".replace(",", " "))
    st.caption(f"NVD sa kontroluje každých {decimal(interval / 60, 0)} min. Stránka sa obnovuje sama. Model: {status.get('model', '')}.")

    if records.empty:
        st.info("Zatiaľ nie sú spracované žiadne zraniteľnosti.")
        return

    columns = st.columns(len(op.ACTION_NAMES))
    for column, action in zip(columns, op.ACTION_NAMES):
        count = int((records["action"] == action).sum())
        column.metric(action, f"{count:,}".replace(",", " "), percent(count / len(records)), delta_color="off", delta_arrow="off")

    scored = records[records["actual_severity"].isin(op.LABELS)]
    if len(scored):
        critical = scored[scored["actual_severity"] == "CRITICAL"]
        recall = (critical["predicted_class"] == "CRITICAL").mean() if len(critical) else None
        st.markdown(
            f"**Kontrola presnosti:** z {len(scored):,} záznamov, ktoré už majú skóre CVSS, model určil správnu triedu pri "
            f"{percent((scored['predicted_class'] == scored['actual_severity']).mean())}".replace(",", " ", 1)
            + (f" a zachytil {percent(recall)} kritických." if recall is not None else ".")
        )

    actions = st.multiselect("Opatrenie", op.ACTION_NAMES, placeholder="Všetky", key="live_actions")
    shown = records[records["action"].isin(actions)] if actions else records
    st.dataframe(
        shown.head(500),
        hide_index=True,
        width="stretch",
        height=420,
        column_order=[
            "published", "cve_id", "action", "predicted_class", "actual_severity",
            "p_critical", "expected_risk", "cwe_text", "description",
        ],
        column_config={
            "published": "zverejnené (UTC)",
            "cve_id": "CVE-ID",
            "action": "opatrenie",
            "predicted_class": "predikcia",
            "actual_severity": "skutočná závažnosť",
            "p_critical": st.column_config.NumberColumn("P(CRITICAL)", format="%.2f"),
            "expected_risk": st.column_config.NumberColumn("denná škoda (€)", format="%.2f"),
            "cwe_text": "CWE",
            "description": st.column_config.TextColumn("popis", width="large"),
        },
    )
    show_model_report()


def assumptions_tab():
    st.warning(
        "Dataset neobsahuje náklady, časy ani skutočné zneužitia. Hodnoty nižšie sú predpoklady pre "
        "modelovú organizáciu a pri reálnom použití ich treba nahradiť jej údajmi."
    )
    st.markdown(f"**Hodinová sadzba:** {op.HOURLY_RATE} €. **Riziko po nasadení dočasnej ochrany:** {percent(op.PROTECTION_RESIDUAL)}.")

    st.markdown("**Opatrenia**")
    st.dataframe(op.ACTION_ASSUMPTIONS.assign(**{"náklady na prácu (€)": op.COST, "efektívne dni expozície": op.EXPOSURE}), width="stretch")
    st.markdown("**Triedy závažnosti**")
    st.dataframe(op.SEVERITY_ASSUMPTIONS.assign(**{"denná očakávaná škoda (€)": op.DAILY_RISK.round(2)}), width="stretch")
    st.markdown("**Prahy pre zmenu opatrenia**")
    st.dataframe(op.thresholds().round(2), hide_index=True, width="stretch")


st.title("Opatrenia pre zraniteľnosti")
st.write("Pridajte zraniteľnosť a model odhadne jej závažnosť a odporučí opatrenie podľa rizika, nákladov a času.")

if not op.active_model_path().exists() and not op.DATA_PATH.exists():
    st.error("Chýbajú vyčistené dáta. Najprv spustite notebook priprava_dat.ipynb.")
    st.stop()

bundle = active_bundle()

tab_new, tab_live, tab_records, tab_overview, tab_assumptions = st.tabs(
    ["Nový záznam", "Živá prevádzka", "Pridané záznamy", "Výsledky na testovacích dátach", "Predpoklady"]
)
with tab_new:
    new_record_tab(bundle)
with tab_live:
    live_tab()
with tab_records:
    records_tab()
with tab_overview:
    overview_tab()
with tab_assumptions:
    assumptions_tab()
