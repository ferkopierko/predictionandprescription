"""Aplikácia: hodnotenie rizika bezpečnostného incidentu a odporúčané opatrenie.

Spustenie: streamlit run app.py
"""

import html
import json
from datetime import datetime

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import opatrenia as op
import preklady as pr

st.set_page_config(page_title="Hodnotenie rizika incidentov", page_icon="🛡️", layout="wide")

PREFIX = "f_"
SELECT_FIELDS = ["odvetvie", "velkost_organizacie", "krajina", "cielenost"]
LIST_FIELDS = ["aktor_typy", "akcia_typy", *op.DETAIL_COLUMNS]
CHECK_FIELDS = ["atribut_integrity", "atribut_availability"]
REQUIRED_SELECTS = ["odvetvie", "velkost_organizacie"]

# Jednotné farby pre celú aplikáciu aj grafy (rovnaké odtiene v svetlom aj tmavom režime)
IMPACT_COLORS = {"nízky": "#2E9E6A", "stredný": "#E09A1F", "vysoký": "#D9463E"}
IMPACT_CLASS = {"nízky": "low", "stredný": "mid", "vysoký": "high"}
OPTION_COLORS = dict(zip(op.OPTION_NAMES, ["#94A3B8", "#4A6EEB", "#8B5CF6", "#14A3A1"]))
COST_COLOR = "#4A6EEB"
RESIDUAL_COLOR = "#A9B4C6"
LABEL_COLOR = "#7A8599"
BUDGET_COLORS = {op.BUDGET_ORDERS[0]: COST_COLOR, op.BUDGET_ORDERS[1]: RESIDUAL_COLOR}

# Slovenský formát čísel (548 250 €, 0,34) a dátumov v grafoch Altair
SK_LOCALE = alt.Locale(
    number=alt.NumberLocale(decimal=",", thousands=" ", grouping=[3], currency=["", " €"]),
    time=alt.TimeLocale(
        dateTime="%A %-d. %B %Y %H:%M:%S", date="%-d. %-m. %Y", time="%H:%M:%S", periods=["", ""],
        days=["nedeľa", "pondelok", "utorok", "streda", "štvrtok", "piatok", "sobota"],
        shortDays=["ne", "po", "ut", "st", "št", "pi", "so"],
        months=["január", "február", "marec", "apríl", "máj", "jún", "júl", "august", "september", "október",
                "november", "december"],
        shortMonths=["jan", "feb", "mar", "apr", "máj", "jún", "júl", "aug", "sep", "okt", "nov", "dec"],
    ),
)
AXIS_FONT = 13

HELP = {
    "aktor_typy": "Kto incident spôsobil. Ak to neviete, vyberte Neznámy.",
    "akcia_typy": "Akým spôsobom incident vznikol. Ak to neviete, vyberte Neznámy.",
    "aktor_variety": "Spresnenie aktéra, napríklad organizovaný zločin alebo správca systému.",
    "akcia_variety": "Spresnenie útoku, napríklad SQL injection alebo doručenie nesprávnemu adresátovi.",
    "akcia_vektory": "Cesta, ktorou útok prišiel, napríklad webová aplikácia alebo príloha e-mailu.",
    "aktivum_variety": "Dotknuté aktíva: server, zariadenie používateľa, nosič dát, osoba, terminál alebo sieťové zariadenie.",
    "typy_dat": "Aké dáta boli ohrozené.",
    "motiv": "Motív aktéra. Ak ho nepoznáte, nechajte prázdne.",
    "sposob_odhalenia": "Kto incident odhalil. Ak to nie je známe, nechajte prázdne.",
}
OPTION_TEXT = {
    "Akceptovať a monitorovať": "Riziko vedome prijať a sledovať výskyt. Pri tejto strate sa žiadne opatrenie nevráti.",
    "Prevencia": "Zaviesť preventívne opatrenia, ktoré znížia počet incidentov tohto vzoru.",
    "Detekcia a reakcia": "Zaviesť detekciu, obnovu a riadenie incidentov, ktoré znížia stratu z incidentu.",
    "Komplexná ochrana": "Zaviesť prevenciu aj detekciu a reakciu. Riziko je také vysoké, že sa oplatí znížiť počet incidentov aj ich dopad.",
}

# Ikona štítu: st.html odstraňuje SVG, preto sa kreslí cez CSS masku (.rk-shield)
SHIELD = '<span class="rk-shield"></span>'
SHIELD_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
    "stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3l7 3v5c0 4.6-3 8.5-7 10-4-1.5-7-5.4-7-10V6l7-3z'/%3E"
    "%3Cpath d='M9 12l2 2 4-4'/%3E%3C/svg%3E"
)

CSS = """
<style>
:root {
  --rk-surface: #ffffff;
  --rk-surface-2: #f1f4f9;
  --rk-border: #dde3ec;
  --rk-muted: #5d6879;
  --rk-primary: #2f5bea;
  --rk-primary-soft: rgba(47, 91, 234, .09);
  --rk-low: #237a52;  --rk-low-bg: rgba(46, 158, 106, .13);
  --rk-mid: #9a6408;  --rk-mid-bg: rgba(224, 154, 31, .17);
  --rk-high: #b8332c; --rk-high-bg: rgba(217, 70, 62, .13);
  --rk-shadow: 0 1px 2px rgba(16, 24, 40, .04), 0 6px 20px rgba(16, 24, 40, .06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --rk-surface: #161c26;
    --rk-surface-2: #1d2531;
    --rk-border: #2b3543;
    --rk-muted: #9aa5b6;
    --rk-primary: #7b97f8;
    --rk-primary-soft: rgba(110, 142, 247, .14);
    --rk-low: #5fd09a;  --rk-low-bg: rgba(63, 185, 127, .16);
    --rk-mid: #f2bb55;  --rk-mid-bg: rgba(237, 170, 54, .16);
    --rk-high: #f08a84; --rk-high-bg: rgba(232, 98, 91, .17);
    --rk-shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 6px 20px rgba(0, 0, 0, .25);
  }
}

/* Skryť ovládanie Streamlitu */
[data-testid="stToolbar"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu,
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stMainBlockContainer"] { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1380px; }
@media (max-width: 900px) { [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; } }

/* Hlavička */
.rk-shield { display: block; width: 26px; height: 26px; background: currentColor;
  -webkit-mask: url("SHIELD_SVG") center / contain no-repeat; mask: url("SHIELD_SVG") center / contain no-repeat; }
.rk-header { display: flex; align-items: flex-start; gap: 14px; margin-bottom: .4rem; }
.rk-header > div:last-child { flex: 1; min-width: 0; }
.rk-logo { width: 46px; height: 46px; border-radius: 12px; display: grid; place-items: center;
  color: #fff; background: linear-gradient(135deg, #2f5bea, #14a3a1); flex: none; }
.rk-title { font-size: 1.55rem; font-weight: 700; letter-spacing: -.01em; line-height: 1.2; }
.rk-subtitle { color: var(--rk-muted); font-size: .95rem; margin-top: 2px; }
.rk-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.rk-chip { font-size: .78rem; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--rk-border);
  color: var(--rk-muted); background: var(--rk-surface); white-space: nowrap; }

/* Záložky */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 4px; }
[data-testid="stTab"] p { font-size: 1rem; font-weight: 600; }

/* Kroky formulára */
.rk-step { display: flex; align-items: center; gap: 10px; font-weight: 650; font-size: 1.02rem; margin: 2px 0 2px; }
.rk-step span { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: .8rem;
  background: var(--rk-primary-soft); color: var(--rk-primary); flex: none; }
.rk-step small { font-weight: 400; color: var(--rk-muted); font-size: .85rem; }
.rk-hint { color: var(--rk-muted); font-size: .86rem; margin: -2px 0 4px; }
.rk-hint b { font-weight: 600; }

/* Karty a ukazovatele */
.rk-card { background: var(--rk-surface); border: 1px solid var(--rk-border); border-radius: 14px;
  box-shadow: var(--rk-shadow); padding: 18px 20px; }
.rk-label { text-transform: uppercase; letter-spacing: .06em; font-size: .72rem; font-weight: 600; color: var(--rk-muted); }
.rk-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 4px 0 14px; }
.rk-kpi { background: var(--rk-surface); border: 1px solid var(--rk-border); border-radius: 12px; padding: 14px 16px; }
.rk-kpi-value { font-size: 1.5rem; font-weight: 700; margin-top: 4px; line-height: 1.25; font-variant-numeric: tabular-nums; }
.rk-note { color: var(--rk-muted); font-size: .84rem; margin-top: 4px; }

/* Výsledok */
.rk-hero { background: var(--rk-surface); border: 1px solid var(--rk-border); border-radius: 16px;
  box-shadow: var(--rk-shadow); overflow: hidden; }
.rk-hero-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 12px 20px; border-bottom: 1px solid var(--rk-border); background: var(--rk-surface-2); }
.rk-hero-top b { font-weight: 650; }
.rk-tag { font-size: .8rem; color: var(--rk-muted); }
.rk-reco { padding: 18px 20px 14px; border-left: 5px solid var(--opt); }
.rk-reco-name { font-size: 1.85rem; font-weight: 700; letter-spacing: -.01em; margin: 2px 0 4px; line-height: 1.2; }
.rk-reco-text { font-size: .95rem; }
.rk-cis { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.rk-cis span { font-size: .8rem; font-weight: 600; padding: 2px 9px; border-radius: 6px;
  background: var(--rk-primary-soft); color: var(--rk-primary); }
.rk-hero .rk-kpis { padding: 0 20px; margin: 4px 0 0; }
.rk-hero .rk-kpi { background: var(--rk-surface-2); border: none; }
.rk-savings { padding: 12px 20px 16px; font-size: .92rem; color: var(--rk-muted); }
.rk-savings b { color: inherit; font-weight: 650; }
.rk-impact { display: inline-block; padding: 1px 12px; border-radius: 999px; font-size: 1.25rem; font-weight: 700; }
.rk-impact.low { color: var(--rk-low); background: var(--rk-low-bg); }
.rk-impact.mid { color: var(--rk-mid); background: var(--rk-mid-bg); }
.rk-impact.high { color: var(--rk-high); background: var(--rk-high-bg); }
.rk-impact.small { font-size: .85rem; padding: 0 9px; }
.rk-verdict { display: flex; gap: 12px; align-items: flex-start; margin: 0 20px 18px; padding: 12px 14px; border-radius: 12px; }
.rk-verdict.ok { background: var(--rk-low-bg); }
.rk-verdict.miss { background: var(--rk-mid-bg); }
.rk-verdict .rk-icon { font-size: 1.1rem; font-weight: 700; line-height: 1.5; }
.rk-verdict.ok .rk-icon { color: var(--rk-low); }
.rk-verdict.miss .rk-icon { color: var(--rk-mid); }
.rk-section { font-weight: 650; margin: 18px 0 2px; }
.rk-empty { text-align: center; padding: 38px 24px; border: 1.5px dashed var(--rk-border); border-radius: 16px; }
.rk-empty-icon { width: 52px; height: 52px; margin: 0 auto 10px; border-radius: 14px; display: grid; place-items: center;
  color: var(--rk-primary); background: var(--rk-primary-soft); }
.rk-empty h4 { margin: 0 0 6px; padding: 0; font-size: 1.1rem; }
.rk-empty p { color: var(--rk-muted); margin: 0 auto; max-width: 400px; font-size: .92rem; }
.rk-demo { display: flex; gap: 10px; align-items: center; padding: 10px 14px; border-radius: 12px;
  background: var(--rk-primary-soft); font-size: .92rem; margin-bottom: 6px; }
.rk-demo b { font-weight: 650; }

/* Živé sledovanie */
.rk-live { display: inline-flex; align-items: center; gap: 8px; font-size: .92rem; color: var(--rk-muted); }
.rk-live b { color: inherit; font-weight: 650; }
.rk-live.on { color: var(--rk-low); }
.rk-live code { font-size: .85rem; }
.rk-dot { width: 10px; height: 10px; border-radius: 50%; background: currentColor; flex: none; }
.rk-live.on .rk-dot { animation: rk-pulse 1.6s ease-out infinite; }
@keyframes rk-pulse { 0% { box-shadow: 0 0 0 0 var(--rk-low-bg); } 70% { box-shadow: 0 0 0 9px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
.rk-feed { overflow-x: auto; border: 1px solid var(--rk-border); border-radius: 12px; background: var(--rk-surface); margin-top: 6px; }
.rk-feed table { width: 100%; border-collapse: collapse; font-size: .88rem; }
.rk-feed th { text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; font-weight: 600;
  color: var(--rk-muted); padding: 9px 12px; border-bottom: 1px solid var(--rk-border); white-space: nowrap; }
.rk-feed td { padding: 7px 12px; border-bottom: 1px solid var(--rk-border); white-space: nowrap; }
.rk-feed tr:last-child td { border-bottom: none; }
.rk-feed .num { text-align: right; font-variant-numeric: tabular-nums; }
.rk-feed th.num { text-align: right; }
.rk-feed tr.new td { animation: rk-flash 2.4s ease-out; }
@keyframes rk-flash { from { background: var(--rk-primary-soft); } to { background: transparent; } }
.rk-hit { color: var(--rk-low); font-weight: 700; }
.rk-miss { color: var(--rk-mid); font-weight: 700; }

/* Panel výsledku ostáva na širokej obrazovke pri posúvaní formulára viditeľný */
@media (min-width: 1100px) {
  .st-key-result_panel { position: sticky; top: 1rem; }
}
/* Na úzkej obrazovke (stĺpce pod sebou) je výsledok nad formulárom */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has(.st-key-has_result) { flex-direction: column-reverse; }
}
.st-key-evaluate button { min-height: 2.9rem; font-size: 1.02rem; font-weight: 600; }
</style>
"""


# ---------------------------------------------------------------- formát čísel

def euro(value):
    return f"{value:,.0f}".replace(",", " ") + " €"


def thousands_euro(value):
    return f"{value / 1000:,.0f}".replace(",", " ") + " tis. €"


def decimal(value, digits=3):
    return f"{value:.{digits}f}".replace(".", ",")


def percent(value):
    return f"{value * 100:.0f} %"


def parse_decimal(text):
    try:
        return float(str(text).strip().replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def date_time(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").strftime("%-d. %-m. %Y %H:%M")
    except (TypeError, ValueError):
        return text


def esc(text):
    return html.escape(str(text))


def impact_pill(label, small=False):
    return f'<span class="rk-impact {IMPACT_CLASS[label]}{" small" if small else ""}">{esc(label)}</span>'


def kpi_row(items):
    cells = "".join(
        f'<div class="rk-kpi"><div class="rk-label">{esc(label)}</div><div class="rk-kpi-value">{value}</div>'
        f'{f"<div class=rk-note>{note}</div>" if note else ""}</div>'
        for label, value, note in items
    )
    return f'<div class="rk-kpis">{cells}</div>'


def step(number, title, note=""):
    st.html(f'<div class="rk-step"><span>{number}</span>{esc(title)}{f" <small>{esc(note)}</small>" if note else ""}</div>')


@st.cache_resource(show_spinner="Načítavam model a dáta…")
def load_context():
    return op.context()


# ---------------------------------------------------------------- stav formulára

def form_values():
    values = {field: st.session_state.get(PREFIX + field) for field in SELECT_FIELDS + LIST_FIELDS + CHECK_FIELDS}
    return {field: list(value or []) if field in LIST_FIELDS else value for field, value in values.items()}


def model_input(values):
    """Nevyplnené povinné výbery nahradí neznámou hodnotou, aby sa dal zobraziť vzor útoku a frekvencia."""
    defaults = op.default_input()
    return {field: defaults[field] if value is None else value for field, value in values.items()}


def set_form(values):
    for field, value in values.items():
        st.session_state[PREFIX + field] = list(value) if isinstance(value, list) else value
    # Frekvencia sa po zmene incidentu znova predvyplní
    st.session_state.pop("frekvencia_pre", None)


def empty_form():
    values = op.default_input()
    for field in REQUIRED_SELECTS:
        values[field] = None
    return values


def init_form():
    if PREFIX + "krajina" not in st.session_state:
        set_form(empty_form())


def fill_random_incident():
    demo = op.random_test_incident()
    set_form(demo["vstup"])
    st.session_state["demo"] = demo
    st.session_state.pop("vysledok", None)
    st.session_state.pop("chyby", None)


def clear_form():
    set_form(empty_form())
    for key in ["demo", "vysledok", "chyby"]:
        st.session_state.pop(key, None)
    st.session_state[PREFIX + "nazov"] = ""


def forget_demo():
    """Po ručnej zmene formulára už skutočný dopad testovacieho incidentu neplatí."""
    st.session_state.pop("demo", None)


def required_errors(values):
    errors = []
    if values["odvetvie"] is None:
        errors.append("Vyberte odvetvie organizácie.")
    if values["velkost_organizacie"] is None:
        errors.append("Vyberte veľkosť organizácie.")
    if not op.actor_types(values):
        errors.append("Vyberte aspoň jeden typ aktéra. Ak aktéra nepoznáte, vyberte Neznámy.")
    if not op.action_types(values):
        errors.append("Vyberte aspoň jeden typ útoku. Ak spôsob nepoznáte, vyberte Neznámy.")
    return errors


def evaluate():
    values = form_values()
    errors = required_errors(values)
    frequency = parse_decimal(st.session_state.get("frekvencia", ""))
    if frequency is None or not 0 <= frequency <= 100:
        errors.append("Frekvencia musí byť číslo od 0 do 100, napríklad 0,25.")
    if not errors:
        errors = op.validate(values)
    if errors:
        st.session_state["chyby"] = errors
        st.session_state.pop("vysledok", None)
        return
    st.session_state.pop("chyby", None)
    result = op.assess(values, frequency)
    demo = st.session_state.get("demo")
    record_id = op.save_assessment(
        values, result, source="aplikácia", name=st.session_state.get(PREFIX + "nazov", ""),
        actual_impact=demo["skutocny_dopad"] if demo else None,
    )
    st.session_state["vysledok"] = (record_id, result, demo, st.session_state.get(PREFIX + "nazov", ""))


# ---------------------------------------------------------------- grafy

def probability_chart(probabilities, actual=None):
    frame = pd.DataFrame({"dopad": op.LABELS, "p": [probabilities[label] for label in op.LABELS]})
    frame["text"] = [percent(p) + ("   ◀ skutočný dopad" if label == actual else "") for label, p in zip(frame["dopad"], frame["p"])]
    base = alt.Chart(frame).encode(
        y=alt.Y("dopad:N", sort=op.LABELS, title=None, axis=alt.Axis(ticks=False, domain=False, labelFontSize=13, labelPadding=8)),
        x=alt.X("p:Q", title=None, axis=None, scale=alt.Scale(domain=[0, 1.45])),
        tooltip=[alt.Tooltip("dopad:N", title="dopad"), alt.Tooltip("text:N", title="pravdepodobnosť")],
    )
    bars = base.mark_bar(cornerRadiusEnd=5, height=22).encode(
        color=alt.Color("dopad:N", scale=alt.Scale(domain=list(IMPACT_COLORS), range=list(IMPACT_COLORS.values())), legend=None)
    )
    labels = base.mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=LABEL_COLOR).encode(text="text:N")
    return (bars + labels).properties(height=125).configure_view(stroke=None)


def cost_chart(comparison):
    rows = []
    for item in comparison:
        name = ("★ " if item["odporucane"] else "") + item["opatrenie"]
        rows.append({"opatrenie": name, "časť": "cena opatrenia", "hodnota": item["cena"], "poradie": 0,
                     "suma": euro(item["cena"])})
        rows.append({"opatrenie": name, "časť": "zostávajúca strata", "hodnota": item["zostavajuca_strata"], "poradie": 1,
                     "suma": euro(item["zostavajuca_strata"])})
    frame = pd.DataFrame(rows)
    order = list(dict.fromkeys(frame["opatrenie"]))
    totals = pd.DataFrame({
        "opatrenie": order,
        "spolu": [item["celkove_naklady"] for item in comparison],
        "text": [euro(item["celkove_naklady"]) for item in comparison],
    })
    top = totals["spolu"].max() * 1.32
    y = alt.Y("opatrenie:N", sort=order, title=None, axis=alt.Axis(ticks=False, domain=False, labelFontSize=13,
                                                                   labelLimit=230, labelPadding=8))
    bars = alt.Chart(frame).mark_bar(height=20).encode(
        y=y,
        x=alt.X("hodnota:Q", stack="zero", title=None, axis=None, scale=alt.Scale(domain=[0, top])),
        color=alt.Color("časť:N", scale=alt.Scale(domain=["cena opatrenia", "zostávajúca strata"],
                                                  range=[COST_COLOR, RESIDUAL_COLOR]),
                        legend=None),
        order=alt.Order("poradie:Q"),
        tooltip=[alt.Tooltip("opatrenie:N"), alt.Tooltip("časť:N"), alt.Tooltip("suma:N", title="suma")],
    )
    labels = alt.Chart(totals).mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=LABEL_COLOR).encode(
        y=y, x="spolu:Q", text="text:N"
    )
    return (bars + labels).properties(height=200).configure_view(stroke=None)


def register_chart(register):
    frame = register.copy()
    frame["strata"] = frame["očakávaná strata (€)"].map(thousands_euro)
    frame["P"] = frame["P(vysoký dopad)"].map(percent)
    frame["cena"] = frame["cena opatrenia (€)"].map(euro)
    frame["prínos"] = frame["čistý prínos (€)"].map(euro)
    frame["frekvencia"] = frame["frekvencia za rok"].map(lambda value: decimal(value))
    sectors = list(dict.fromkeys(frame.sort_values("odvetvie")["odvetvie"]))
    base = alt.Chart(frame).encode(
        x=alt.X("odvetvie:N", sort=sectors, title=None, scale=alt.Scale(paddingInner=0.05),
                axis=alt.Axis(orient="top", labelAngle=0, labelLimit=150, ticks=False, domain=False, labelFontSize=12)),
        y=alt.Y("vzor_utoku:N", sort=op.PATTERNS, title=None, scale=alt.Scale(paddingInner=0.08),
                axis=alt.Axis(ticks=False, domain=False, labelFontSize=12, labelLimit=220, labelPadding=8)),
    )
    cells = base.mark_rect(cornerRadius=6).encode(
        color=alt.Color("opatrenie:N", scale=alt.Scale(domain=list(OPTION_COLORS), range=list(OPTION_COLORS.values())),
                        legend=alt.Legend(orient="bottom", title=None, labelFontSize=12, columns=4, symbolType="square")),
        tooltip=[
            alt.Tooltip("odvetvie:N"), alt.Tooltip("vzor_utoku:N", title="vzor útoku"),
            alt.Tooltip("frekvencia:N", title="frekvencia za rok"), alt.Tooltip("P:N", title="P(vysoký dopad)"),
            alt.Tooltip("strata:N", title="očakávaná strata"), alt.Tooltip("opatrenie:N"),
            alt.Tooltip("opatrenia CIS:N", title="opatrenia CIS"), alt.Tooltip("cena:N", title="cena opatrenia"),
            alt.Tooltip("prínos:N", title="čistý prínos"),
        ],
    )
    text = base.mark_text(fontSize=12, fontWeight=600, color="#ffffff").encode(text="strata:N")
    return finish((cells + text).properties(height=430))


def finish(chart):
    """Spoločný vzhľad grafov: slovenský formát, väčšie popisy, bez rámčeka."""
    return (
        chart.configure(locale=SK_LOCALE)
        .configure_view(stroke=None)
        .configure_axis(labelFontSize=AXIS_FONT, titleFontSize=AXIS_FONT, titleFontWeight=500, titlePadding=10)
        .configure_legend(labelFontSize=AXIS_FONT, symbolSize=140)
    )


def budget_chart(curves, budget):
    """Krivka zníženej straty podľa rozpočtu pre obe poradia a bod pre zvolený rozpočet."""
    rows, marks = [], []
    for name, steps in curves.items():
        rows.append({"poradie": name, "rozpočet": 0.0, "strata": 0.0, "scenár": "–", "opatrenie": "–", "krok": 0})
        rows += [
            {"poradie": name, "rozpočet": row["rozpočet (€)"], "strata": row["znížená strata spolu (€)"],
             "scenár": f'{row["odvetvie"]}: {row["vzor_utoku"]}', "opatrenie": row["opatrenie"], "krok": row["poradie"]}
            for _, row in steps.iterrows()
        ]
        covered, reduced = op.budget_coverage(budget, name)
        marks.append({"poradie": name, "rozpočet": budget, "strata": reduced, "text": euro(reduced),
                      "scenáre": len(covered), "vyššie": None})
    frame = pd.DataFrame(rows)
    frame["rozpočet text"] = frame["rozpočet"].map(euro)
    frame["strata text"] = frame["strata"].map(euro)
    marks = pd.DataFrame(marks)
    # Vyšší bod má popis nad sebou, nižší pod sebou, aby sa pri blízkych hodnotách neprekrývali
    marks["vyššie"] = marks["strata"] >= marks["strata"].max()
    top = frame["strata"].max() * 1.08
    scale = alt.Scale(domain=list(BUDGET_COLORS), range=list(BUDGET_COLORS.values()))
    color = alt.Color("poradie:N", scale=scale, legend=alt.Legend(orient="bottom", title=None, direction="horizontal"))
    x = alt.X("rozpočet:Q", title="Ročný rozpočet na opatrenia (€)",
              scale=alt.Scale(domain=[0, frame["rozpočet"].max()], nice=False),
              axis=alt.Axis(format=",.0f", tickCount=6, labelFlush=True))
    y = alt.Y("strata:Q", title="Znížená strata pri skutočnom dopade (€ za rok)", scale=alt.Scale(domain=[0, top]),
              axis=alt.Axis(format=",.0f", tickCount=6))
    line = alt.Chart(frame).mark_line(interpolate="step-after", strokeWidth=3).encode(x=x, y=y, color=color)
    steps = alt.Chart(frame[frame["krok"] > 0]).mark_circle(size=55, opacity=0.9).encode(
        x=x, y=y, color=alt.Color("poradie:N", scale=scale, legend=None),
        tooltip=[alt.Tooltip("poradie:N"), alt.Tooltip("krok:Q", title="krok"), alt.Tooltip("scenár:N"),
                 alt.Tooltip("opatrenie:N"), alt.Tooltip("rozpočet text:N", title="rozpočet spolu"),
                 alt.Tooltip("strata text:N", title="znížená strata spolu")],
    )
    rule = alt.Chart(pd.DataFrame({"rozpočet": [budget]})).mark_rule(strokeDash=[6, 4], color=LABEL_COLOR, strokeWidth=1.5) \
        .encode(x="rozpočet:Q")
    points = alt.Chart(marks).mark_point(size=260, filled=True, stroke="#ffffff", strokeWidth=2, opacity=1).encode(
        x=x, y=y, color=alt.Color("poradie:N", scale=scale, legend=None),
        tooltip=[alt.Tooltip("poradie:N"), alt.Tooltip("text:N", title="znížená strata"),
                 alt.Tooltip("scenáre:Q", title="pokryté scenáre")],
    )
    labels = [
        alt.Chart(marks[marks["vyššie"] == upper]).mark_text(align="left", dx=12, dy=-14 if upper else 16, fontSize=13,
                                                            fontWeight=700)
        .encode(x=x, y=y, text="text:N", color=alt.Color("poradie:N", scale=scale, legend=None))
        for upper in (True, False)
    ]
    return finish(alt.layer(line, steps, rule, points, *labels).properties(height=420))


def strategy_chart(strategies):
    """Vodorovné stĺpce ročných nákladov stratégií na organizáciu, naše riešenie zvýraznené."""
    frame = strategies.copy()
    frame["text"] = frame["na organizáciu (€)"].map(euro)
    frame["spolu"] = frame["ročné náklady spolu (€)"].map(euro)
    frame["skupina"] = np.where(frame["naša"], "naše riešenie", "ostatné stratégie")
    order = list(frame["stratégia"])
    y = alt.Y("stratégia:N", sort=order, title=None,
              axis=alt.Axis(ticks=False, domain=False, labelLimit=360, labelPadding=8))
    x = alt.X("na organizáciu (€):Q", title=None, axis=None,
              scale=alt.Scale(domain=[0, frame["na organizáciu (€)"].max() * 1.2]))
    tooltip = [alt.Tooltip("stratégia:N"), alt.Tooltip("text:N", title="na organizáciu za rok"),
               alt.Tooltip("spolu:N", title="spolu za 6 organizácií")]
    bars = alt.Chart(frame).mark_bar(height=22, cornerRadiusEnd=4).encode(
        y=y, x=x, tooltip=tooltip,
        color=alt.Color("skupina:N", scale=alt.Scale(domain=["naše riešenie", "ostatné stratégie"],
                                                     range=[COST_COLOR, RESIDUAL_COLOR]), legend=None),
    )
    labels = alt.Chart(frame[~frame["naša"]]).mark_text(align="left", dx=6, fontSize=13, fontWeight=500,
                                                       color=LABEL_COLOR).encode(y=y, x=x, text="text:N")
    ours = alt.Chart(frame[frame["naša"]]).mark_text(align="left", dx=6, fontSize=14, fontWeight=700,
                                                     color=COST_COLOR).encode(y=y, x=x, text="text:N")
    return finish((bars + labels + ours).properties(height=38 * len(frame)))


def _time_axis(times):
    """Os času: hodiny v rámci dňa, inak jedna značka na deň, týždeň alebo mesiac, aby sa dátum neopakoval."""
    span = times.max() - times.min()
    if span < pd.Timedelta(hours=20):
        return alt.Axis(format="%H:%M", labelFlush=True, tickCount=6)
    if span < pd.Timedelta(days=14):
        interval = {"interval": "day", "step": 1}
    elif span < pd.Timedelta(days=90):
        interval = {"interval": "week", "step": 1}
    else:
        return alt.Axis(format="%-m. %Y", labelFlush=True, tickCount={"interval": "month", "step": 1})
    return alt.Axis(format="%-d. %-m.", labelFlush=True, tickCount=interval)


def _padded(timeline, columns):
    """Pridá nulový bod pred prvé a posledný stav za posledné hodnotenie, aby bol vidieť aj jediný záznam."""
    times = timeline["čas"]
    pad = max((times.max() - times.min()) * 0.04, pd.Timedelta(minutes=1))
    start = {column: 0 for column in columns} | {"čas": times.min() - pad}
    end = timeline.iloc[-1][columns].to_dict() | {"čas": times.max() + pad}
    return pd.concat([pd.DataFrame([start]), timeline[["čas", *columns]], pd.DataFrame([end])], ignore_index=True)


def impact_timeline_chart(timeline):
    """Kumulatívny počet hodnotení v čase podľa predikovaného dopadu."""
    columns = [f"počet {label}" for label in op.LABELS]
    frame = _padded(timeline, columns).melt("čas", columns, var_name="dopad", value_name="počet")
    frame["dopad"] = frame["dopad"].str.removeprefix("počet ")
    frame["čas text"] = frame["čas"].dt.strftime("%-d. %-m. %Y %H:%M")
    x = alt.X("čas:T", title=None, axis=_time_axis(timeline["čas"]))
    area = alt.Chart(frame).mark_area(interpolate="step-after", opacity=0.88).encode(
        x=x,
        y=alt.Y("počet:Q", stack="zero", title="Počet hodnotení spolu", axis=alt.Axis(format="d", tickMinStep=1)),
        color=alt.Color("dopad:N", sort=op.LABELS, scale=alt.Scale(domain=list(IMPACT_COLORS), range=list(IMPACT_COLORS.values())),
                        legend=alt.Legend(orient="bottom", title="Predikovaný dopad", direction="horizontal")),
        order=alt.Order("poradie:Q"),
        tooltip=[alt.Tooltip("dopad:N"), alt.Tooltip("počet:Q", title="počet do tohto času"), alt.Tooltip("čas text:N", title="čas")],
    ).transform_calculate(poradie="indexof(['nízky', 'stredný', 'vysoký'], datum.dopad)")
    return finish(area.properties(height=300))


REDUCTION_COLOR = IMPACT_COLORS["nízky"]


def loss_by_sector_chart(records):
    """Očakávaná ročná strata podľa odvetvia pred opatrením a po ňom.

    Celý stĺpec je strata pred opatrením, sivá časť strata, ktorá po odporúčanom opatrení zostane,
    zelená časť strata, ktorú opatrenie odstráni.
    """
    sectors = (records.groupby("odvetvie")
               .agg(hodnotenia=("id", "size"), pred=("ocakavana_strata", "sum"), po=("zostavajuca_strata", "sum"),
                    cena=("cena_opatrenia", "sum"))
               .sort_values("pred", ascending=False).reset_index())
    sectors["zníženie"] = sectors["pred"] - sectors["po"]
    sectors["pred text"] = sectors["pred"].map(euro)
    sectors["po text"] = sectors["po"].map(euro)
    sectors["zníženie text"] = sectors["zníženie"].map(euro) + " (" + (sectors["zníženie"] / sectors["pred"].where(
        sectors["pred"] > 0, 1)).map(percent) + ")"
    sectors["cena text"] = sectors["cena"].map(euro)
    sectors["text"] = sectors["pred text"] + " → " + sectors["po text"]
    parts = ["po opatrení zostane", "opatrenie odstráni"]
    frame = sectors.melt(id_vars=[column for column in sectors.columns if column not in ("po", "zníženie")],
                         value_vars=["po", "zníženie"], var_name="časť", value_name="hodnota")
    frame["časť"] = frame["časť"].map({"po": parts[0], "zníženie": parts[1]})
    frame["poradie"] = frame["časť"].map({parts[0]: 0, parts[1]: 1})
    order = list(sectors["odvetvie"])
    y = alt.Y("odvetvie:N", sort=order, title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=220, labelPadding=8))
    x = alt.X("hodnota:Q", stack="zero", title=None, axis=None, scale=alt.Scale(domain=[0, sectors["pred"].max() * 1.55]))
    tooltip = [alt.Tooltip("odvetvie:N"), alt.Tooltip("hodnotenia:Q", title="hodnotení"),
               alt.Tooltip("pred text:N", title="strata pred opatrením"), alt.Tooltip("po text:N", title="strata po opatrení"),
               alt.Tooltip("zníženie text:N", title="zníženie"), alt.Tooltip("cena text:N", title="cena opatrení")]
    bars = alt.Chart(frame).mark_bar(height=24).encode(
        y=y, x=x, order=alt.Order("poradie:Q"), tooltip=tooltip,
        color=alt.Color("časť:N", sort=parts, scale=alt.Scale(domain=parts, range=[RESIDUAL_COLOR, REDUCTION_COLOR]),
                        legend=alt.Legend(orient="bottom", title=None, direction="horizontal")),
    )
    labels = alt.Chart(sectors).mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=LABEL_COLOR).encode(
        y=y, x=alt.X("pred:Q", scale=alt.Scale(domain=[0, sectors["pred"].max() * 1.55])), text="text:N", tooltip=tooltip)
    return finish((bars + labels).properties(height=max(44 * len(sectors), 90)))


def options_chart(records):
    """Koľkokrát bolo odporúčané každé opatrenie, v pevnom poradí a farbách opatrení."""
    counts = records["opatrenie"].value_counts().reindex(op.OPTION_NAMES, fill_value=0)
    frame = pd.DataFrame({"opatrenie": counts.index, "počet": counts.to_numpy()})
    frame["podiel"] = (frame["počet"] / max(len(records), 1)).map(percent)
    frame["text"] = frame["počet"].astype(str) + " (" + frame["podiel"] + ")"
    y = alt.Y("opatrenie:N", sort=op.OPTION_NAMES, title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=260, labelPadding=8))
    x = alt.X("počet:Q", title=None, axis=None, scale=alt.Scale(domain=[0, max(frame["počet"].max(), 1) * 1.3]))
    bars = alt.Chart(frame).mark_bar(height=24, cornerRadiusEnd=4).encode(
        y=y, x=x, color=alt.Color("opatrenie:N", scale=alt.Scale(domain=list(OPTION_COLORS), range=list(OPTION_COLORS.values())),
                                  legend=None),
        tooltip=[alt.Tooltip("opatrenie:N"), alt.Tooltip("počet:Q", title="počet"), alt.Tooltip("podiel:N")],
    )
    labels = alt.Chart(frame).mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=LABEL_COLOR).encode(
        y=y, x=x, text="text:N")
    return finish((bars + labels).properties(height=44 * len(frame)))


def patterns_chart(records, top=8):
    """Najčastejšie vzory útokov v uložených hodnoteniach s ich očakávanou stratou."""
    frame = (records.groupby("vzor_utoku")
             .agg(počet=("id", "size"), strata=("ocakavana_strata", "sum"))
             .sort_values(["počet", "strata"], ascending=False).head(top).reset_index())
    frame["strata text"] = frame["strata"].map(euro)
    frame["text"] = frame["počet"].astype(str)
    order = list(frame["vzor_utoku"])
    y = alt.Y("vzor_utoku:N", sort=order, title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=260, labelPadding=8))
    x = alt.X("počet:Q", title=None, axis=None, scale=alt.Scale(domain=[0, frame["počet"].max() * 1.2]))
    tooltip = [alt.Tooltip("vzor_utoku:N", title="vzor útoku"), alt.Tooltip("počet:Q", title="počet"),
               alt.Tooltip("strata text:N", title="očakávaná strata spolu")]
    bars = alt.Chart(frame).mark_bar(height=24, cornerRadiusEnd=4, color=COST_COLOR).encode(y=y, x=x, tooltip=tooltip)
    labels = alt.Chart(frame).mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=LABEL_COLOR).encode(
        y=y, x=x, text="text:N")
    return finish((bars + labels).properties(height=44 * len(frame)))


# ---------------------------------------------------------------- výsledok

def result_html(record_id, result, demo, name):
    option = result["opatrenie"]
    predicted = result["predikovany_dopad"]
    controls = [item.strip() for item in str(result["opatrenia_cis"]).split(",") if item.strip()]
    cis = ""
    if option != op.OPTION_NAMES[0] and controls:
        cis = '<div class="rk-cis">' + "".join(f"<span>{esc(item)}</span>" for item in controls) + "</div>"
    title = f"Hodnotenie č. {record_id}" + (f" · {esc(name)}" if name else "")

    if option == op.OPTION_NAMES[0]:
        savings = (f"Stačí monitorovanie za <b>{euro(result['cena_opatrenia'])}</b> ročne. "
                   "Každé opatrenie by stálo viac, než by ušetrilo.")
    else:
        savings = (f"Opatrenie stojí <b>{euro(result['cena_opatrenia'])}</b> ročne, znižuje očakávanú stratu na "
                   f"<b>{euro(result['zostavajuca_strata'])}</b> a oproti nečinnosti ušetrí "
                   f"<b>{euro(result['cisty_prinos'])}</b> ročne.")

    verdict = ""
    if demo:
        actual = demo["skutocny_dopad"]
        hit = actual == predicted
        records = f"{demo['pocet_zaznamov']:,}".replace(",", " ")
        verdict = (
            f'<div class="rk-verdict {"ok" if hit else "miss"}"><div class="rk-icon">{"✓" if hit else "!"}</div><div>'
            f'<b>Skutočný dopad testovacieho incidentu:</b> {impact_pill(actual, small=True)} '
            f'<span class="rk-note">({records} uniknutých záznamov)</span><br>'
            f'{"Model predikoval správnu triedu." if hit else "Model predikoval inú triedu dopadu."}</div></div>'
        )

    kpis = kpi_row([
        ("Predikovaný dopad", impact_pill(predicted),
         f"pravdepodobnosť {percent(result['pravdepodobnosti'][predicted])}"),
        ("Očakávaná ročná strata", euro(result["ocakavana_strata"]),
         f"{decimal(result['frekvencia'])} incidentu ročne × {euro(result['strata_incidentu'])}"),
    ])
    return (
        f'<div class="rk-hero">'
        f'<div class="rk-hero-top"><b>{title}</b><span class="rk-tag">{esc(result["odvetvie"])} · {esc(result["vzor_utoku"])}</span></div>'
        f'<div class="rk-reco" style="--opt:{OPTION_COLORS[option]}"><div class="rk-label">Odporúčané opatrenie</div>'
        f'<div class="rk-reco-name">{esc(option)}</div><div class="rk-reco-text">{esc(OPTION_TEXT[option])}</div>{cis}</div>'
        f'{kpis}<div class="rk-savings">{savings}</div>{verdict}</div>'
    )


def show_result(record_id, result, demo, name):
    st.html(result_html(record_id, result, demo, name))

    st.html('<div class="rk-section">Pravdepodobnosť dopadu</div>')
    st.altair_chart(probability_chart(result["pravdepodobnosti"], demo and demo["skutocny_dopad"]), width="stretch")

    st.html('<div class="rk-section">Ročné náklady podľa opatrenia</div>'
            '<div class="rk-note"><b style="color:#4A6EEB">■</b> cena opatrenia + <b style="color:#A9B4C6">■</b> strata, ktorá '
            'zostane. Hviezdička označuje najlacnejšiu možnosť.</div>')
    st.altair_chart(cost_chart(result["porovnanie"]), width="stretch")

    with st.expander("Podrobné porovnanie opatrení"):
        comparison = pd.DataFrame(result["porovnanie"])
        comparison["odporucane"] = comparison["odporucane"].map({True: "áno", False: ""})
        styled = comparison.style.format({"cena": euro, "zostavajuca_strata": euro, "celkove_naklady": euro})
        st.dataframe(
            styled, hide_index=True, width="stretch",
            column_order=["opatrenie", "odporucane", "cena", "zostavajuca_strata", "celkove_naklady", "opatrenia_cis"],
            column_config={
                "opatrenie": "Opatrenie", "odporucane": "Odporúčané", "cena": "Cena",
                "zostavajuca_strata": "Zostávajúca strata", "celkove_naklady": "Spolu", "opatrenia_cis": "Opatrenia CIS",
            },
        )
    st.caption("Sumy vychádzajú z predpokladov na záložke Predpoklady. Výsledok je prvotné posúdenie a nenahrádza analytika.")


def empty_result():
    st.html(
        f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Výsledok hodnotenia</h4>'
        '<p>Vyplňte štyri povinné údaje vľavo a kliknite na <b>Vyhodnotiť riziko</b>. Na rýchlu ukážku použite '
        '<b>Náhodný incident</b> z testovacích dát, pri ňom uvidíte aj skutočný dopad.</p></div>'
    )


# ---------------------------------------------------------------- záložky

def detail_select(column, field, options):
    column.multiselect(
        op.FIELD_NAMES[field].capitalize(), options[field], key=PREFIX + field, help=HELP[field],
        placeholder="Vyberte", format_func=pr.formatter(field), on_change=forget_demo,
    )


def incident_form(options):
    buttons = st.columns(2)
    buttons[0].button("Náhodný incident", icon=":material/casino:", on_click=fill_random_incident, width="stretch",
                      help="Vyplní formulár incidentom z testovacej časti dát, ktorý model pri učení nevidel.")
    buttons[1].button("Vyčistiť formulár", icon=":material/restart_alt:", on_click=clear_form, width="stretch")

    demo = st.session_state.get("demo")
    if demo:
        year = f" z roku {demo['rok']}" if demo["rok"] else ""
        st.html(f'<div class="rk-demo">🎲<div><b>Testovací incident č. {demo["zaznam_id"]}{year}.</b> '
                'Skutočný dopad uvidíte po vyhodnotení.</div></div>')
        if demo["popis"]:
            with st.expander("Popis incidentu z VCDB (model ho nepoužíva)"):
                st.write(demo["popis"])

    with st.container(border=True):
        step(1, "Povinné údaje")
        st.selectbox("Odvetvie", options["odvetvie"], key=PREFIX + "odvetvie", index=None,
                     placeholder="Vyberte odvetvie", on_change=forget_demo)
        st.segmented_control("Veľkosť organizácie", options["velkost_organizacie"], key=PREFIX + "velkost_organizacie",
                                format_func=str.capitalize, on_change=forget_demo, width="stretch")
        st.pills("Typ aktéra", options["aktor_typy"], selection_mode="multi", key=PREFIX + "aktor_typy",
                 format_func=pr.formatter("aktor_typy"), help=HELP["aktor_typy"], on_change=forget_demo)
        st.pills("Typ útoku", options["akcia_typy"], selection_mode="multi", key=PREFIX + "akcia_typy",
                 format_func=pr.formatter("akcia_typy"), help=HELP["akcia_typy"], on_change=forget_demo)

    values = form_values()
    defaults = op.default_input()
    filled = sum(bool(values[field]) for field in op.DETAIL_COLUMNS) + sum(bool(values[field]) for field in CHECK_FIELDS) \
        + sum(values[field] != defaults[field] for field in ["krajina", "cielenost"])
    label = "Podrobnosti incidentu (nepovinné)" + (f" · vyplnené {filled}" if filled else "")
    with st.expander(label, expanded=filled > 0, icon=":material/tune:"):
        st.html('<div class="rk-hint">Čím viac údajov zadáte, tým presnejší je odhad. Neznáme polia nechajte prázdne.</div>')
        left, right = st.columns(2)
        countries = options["krajina"][:5] + sorted(options["krajina"][5:], key=pr.formatter("krajina"))
        left.selectbox("Krajina", countries, key=PREFIX + "krajina", format_func=pr.formatter("krajina"), on_change=forget_demo)
        right.segmented_control("Cielenosť útoku", options["cielenost"], key=PREFIX + "cielenost",
                                format_func=str.capitalize, on_change=forget_demo, width="stretch")
        for field_left, field_right in [("aktor_variety", "akcia_variety"), ("motiv", "akcia_vektory"),
                                        ("aktivum_variety", "typy_dat")]:
            detail_select(left, field_left, options)
            detail_select(right, field_right, options)
        detail_select(left, "sposob_odhalenia", options)
        right.toggle("Narušená integrita", key=PREFIX + "atribut_integrity", on_change=forget_demo,
                     help="Údaje alebo systém boli zmenené.")
        right.toggle("Narušená dostupnosť", key=PREFIX + "atribut_availability", on_change=forget_demo,
                     help="Údaje alebo služba neboli dostupné.")

    row = op.to_row(model_input(form_values()))
    pair = (row["odvetvie"], row["vzor_utoku"])
    default = op.default_frequency(*pair)
    if st.session_state.get("frekvencia_pre") != pair:
        st.session_state["frekvencia"] = decimal(default, 4)
        st.session_state["frekvencia_pre"] = pair

    with st.container(border=True):
        step(2, "Hodnotenie")
        st.html(f'<div class="rk-hint">Vzor útoku podľa zadaných údajov: <b>{esc(row["vzor_utoku"])}</b>. '
                f'Predvolená frekvencia pre odvetvie {esc(row["odvetvie"])}: <b>{decimal(default)}</b> incidentu ročne.</div>')
        left, right = st.columns([1, 1.6])
        left.text_input("Ročná frekvencia incidentov", key="frekvencia",
                        help="Predvyplnená podielom vzoru v odvetví medzi reprezentatívnymi incidentmi pri jednom "
                             "závažnom incidente ročne. Desatinné čísla píšte s čiarkou.")
        right.text_input("Názov hodnotenia (nepovinné)", key=PREFIX + "nazov", max_chars=200,
                         placeholder="napríklad Únik z e-shopu, marec 2026")
        with st.container(key="evaluate"):
            st.button("Vyhodnotiť riziko a uložiť", type="primary", icon=":material/shield:", width="stretch",
                      on_click=evaluate)
        for error in st.session_state.get("chyby", []):
            st.error(error, icon=":material/error:")


def new_assessment_tab():
    options = op.choices()
    init_form()
    form_column, result_column = st.columns([1.08, 1], gap="large")
    with form_column:
        incident_form(options)
    with result_column, st.container(key="result_panel"):
        if "vysledok" in st.session_state:
            with st.container(key="has_result"):
                show_result(*st.session_state["vysledok"])
        else:
            empty_result()


def readable_input(raw):
    incident = json.loads(raw)
    lines = []
    for field in SELECT_FIELDS + LIST_FIELDS:
        value = incident.get(field)
        if not value:
            continue
        values = value if isinstance(value, list) else [value]
        lines.append(f"**{op.FIELD_NAMES[field].capitalize()}:** " + ", ".join(pr.label(field, item) for item in values))
    flags = [text for field, text in [("atribut_integrity", "integrita"), ("atribut_availability", "dostupnosť")]
             if incident.get(field)]
    if flags:
        lines.append("**Narušená:** " + ", ".join(flags))
    return "  \n".join(lines)


def records_tab():
    records = op.load_assessments()
    if records.empty:
        st.html(f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Zatiaľ žiadne hodnotenia</h4>'
                '<p>Pridajte prvé na záložke Nové hodnotenie alebo cez API.</p></div>')
        return

    records.insert(0, "priorita", range(1, len(records) + 1))
    known = records.dropna(subset=["skutocny_dopad"])
    known = known[known["skutocny_dopad"].astype(str).str.len() > 0]
    accuracy = (f"{percent((known['skutocny_dopad'] == known['predikovany_dopad']).mean())}",
                f"z {len(known)} testovacích incidentov") if len(known) else ("–", "žiadne testovacie incidenty")
    st.html(kpi_row([
        ("Uložené hodnotenia", str(len(records)), f"databáza {esc(op.DB_PATH.name)}"),
        ("Očakávaná strata spolu", euro(records["ocakavana_strata"].sum()), "ročne, pred opatreniami"),
        ("Odporúčané opatrenia", euro(records["cena_opatrenia"].sum()), "ročná cena vrátane monitorovania"),
        ("Zhoda so skutočným dopadom", *accuracy),
    ]))
    st.caption("Zoradené od najvyššej očakávanej ročnej straty. Priorita je poradie riešenia.")

    shown = records.drop(columns="vstup").copy()
    shown["vytvorene"] = shown["vytvorene"].map(date_time)
    shown["skutocny_dopad"] = shown["skutocny_dopad"].fillna("–").replace("", "–")
    styled = shown.style.format({
        "ocakavana_strata": euro, "cena_opatrenia": euro, "cisty_prinos": euro,
        "p_nizky": percent, "p_stredny": percent, "p_vysoky": percent,
        "frekvencia": lambda value: decimal(value),
    })
    columns = [
        "priorita", "id", "nazov", "odvetvie", "vzor_utoku", "opatrenie", "ocakavana_strata",
        "predikovany_dopad", "skutocny_dopad", "p_nizky", "p_stredny", "p_vysoky", "frekvencia",
        "opatrenia_cis", "cena_opatrenia", "cisty_prinos", "zdroj", "vytvorene",
    ]
    if shown["nazov"].fillna("").str.strip().eq("").all():
        columns.remove("nazov")
    st.dataframe(
        styled, hide_index=True, width="stretch",
        column_order=columns,
        column_config={
            "priorita": st.column_config.NumberColumn("Priorita", width="small"),
            "id": st.column_config.NumberColumn("Č.", width="small"),
            "nazov": "Názov", "odvetvie": "Odvetvie", "vzor_utoku": "Vzor útoku", "opatrenie": "Opatrenie",
            "ocakavana_strata": "Očakávaná strata", "predikovany_dopad": "Predikovaný dopad",
            "skutocny_dopad": "Skutočný dopad", "p_nizky": "P(nízky)", "p_stredny": "P(stredný)", "p_vysoky": "P(vysoký)",
            "frekvencia": "Frekvencia", "opatrenia_cis": "Opatrenia CIS", "cena_opatrenia": "Cena opatrenia",
            "cisty_prinos": "Čistý prínos", "zdroj": "Zdroj", "vytvorene": "Vytvorené",
        },
    )

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        with st.expander("Vstup hodnotenia", icon=":material/description:"):
            chosen = st.selectbox("Hodnotenie", records["id"], format_func=lambda value: f"č. {value}")
            st.markdown(readable_input(records.loc[records["id"] == chosen, "vstup"].iloc[0]))
        st.download_button("Stiahnuť ako CSV", records.to_csv(index=False).encode("utf-8-sig"), file_name="hodnotenia.csv",
                           mime="text/csv", icon=":material/download:")
    with right:
        labels = {
            row.id: f"{row.priorita}. č. {row.id}{' ' + row.nazov if row.nazov else ''} "
                    f"({row.odvetvie}, {row.vzor_utoku}, {euro(row.ocakavana_strata)})"
            for row in records.itertuples()
        }
        with st.expander("Vymazať hodnotenia", icon=":material/delete:"):
            with st.form("delete_records", border=False):
                to_delete = st.multiselect("Hodnotenia na vymazanie", list(labels), format_func=labels.get,
                                           placeholder="Vyberte hodnotenia")
                delete_all = st.checkbox("Vymazať všetky hodnotenia")
                if st.form_submit_button("Vymazať", icon=":material/delete:"):
                    ids = list(labels) if delete_all else to_delete
                    if ids:
                        op.delete_assessments(ids)
                        st.session_state.pop("vysledok", None)
                        st.rerun()


@st.fragment(run_every=5)
def overview_tab():
    """Grafy z uložených hodnotení. Obnovujú sa každých 5 sekúnd, aby bolo vidieť aj hodnotenia z API."""
    records = op.load_assessments()
    if records.empty:
        st.html(f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Zatiaľ nie je čo zobraziť</h4>'
                '<p>Grafy sa objavia po prvom hodnotení. Pridajte ho na záložke Nové hodnotenie, tlačidlom '
                '<b>Náhodný incident</b> alebo cez API.</p></div>')
        return
    timeline = op.assessment_timeline(records)
    last = timeline.iloc[-1]
    top_option = records["opatrenie"].value_counts().idxmax()
    st.html(kpi_row([
        ("Hodnotenia", str(len(records)), f"posledné {esc(date_time(last['vytvorene']))}"),
        ("Očakávaná strata spolu", euro(records["ocakavana_strata"].sum()), "ročne, pred opatreniami"),
        ("Vysoký dopad", str(int((records["predikovany_dopad"] == "vysoký").sum())), "predikovaný"),
        ("Najčastejšie opatrenie", esc(top_option), f"{int((records['opatrenie'] == top_option).sum())}× odporúčané"),
    ]))
    st.html('<div class="rk-section">Počet hodnotení v čase podľa predikovaného dopadu</div>')
    st.altair_chart(impact_timeline_chart(timeline), width="stretch")
    before, after = records["ocakavana_strata"].sum(), records["zostavajuca_strata"].sum()
    st.html('<div class="rk-section">Očakávaná ročná strata pred opatrením a po ňom podľa odvetvia</div>'
            f'<div class="rk-note">Spolu {esc(euro(before))} pred opatreniami a {esc(euro(after))} po odporúčaných '
            f'opatreniach, teda o {esc(percent((before - after) / before) if before else "0 %")} menej. Ročná cena '
            f'opatrení je {esc(euro(records["cena_opatrenia"].sum()))}.</div>')
    st.altair_chart(loss_by_sector_chart(records), width="stretch")
    st.html('<div class="rk-section">Odporúčané opatrenia</div>')
    st.altair_chart(options_chart(records), width="stretch")
    st.html('<div class="rk-section">Najčastejšie vzory útokov</div>')
    st.altair_chart(patterns_chart(records), width="stretch")
    st.caption("Grafy sa obnovujú automaticky každých 5 sekúnd, takže zahŕňajú aj hodnotenia pridané cez API.")


# ---------------------------------------------------------------- živé sledovanie

LIVE_SOURCE = "simulácia"
LIVE_REFRESH = 2       # sekundy medzi obnoveniami záložky
LIVE_WINDOW = 60       # počet posledných incidentov v grafoch
LIVE_FEED = 12         # počet riadkov v zozname posledných incidentov
LIVE_IDLE = 15         # po koľkých sekundách bez incidentu považujeme generátor za zastavený


def live_loss_chart(frame):
    """Očakávaná ročná strata každého incidentu v čase, farba podľa predikovaného dopadu."""
    data = frame.copy()
    data["čas text"] = data["čas"].dt.strftime("%H:%M:%S")
    data["strata text"] = data["ocakavana_strata"].map(euro)
    data["skutočný"] = data["skutocny_dopad"].fillna("–").replace("", "–")
    x = alt.X("čas:T", title=None, axis=alt.Axis(format="%H:%M:%S", labelFlush=True, tickCount=6))
    y = alt.Y("ocakavana_strata:Q", title="Očakávaná ročná strata (€)", scale=alt.Scale(type="sqrt"),
              axis=alt.Axis(format=",.0f"))
    color = alt.Color("predikovany_dopad:N", sort=op.LABELS,
                      scale=alt.Scale(domain=list(IMPACT_COLORS), range=list(IMPACT_COLORS.values())),
                      legend=alt.Legend(orient="bottom", title="Predikovaný dopad", direction="horizontal"))
    tooltip = [alt.Tooltip("čas text:N", title="čas"), alt.Tooltip("nazov:N", title="incident"),
               alt.Tooltip("odvetvie:N"), alt.Tooltip("vzor_utoku:N", title="vzor útoku"),
               alt.Tooltip("predikovany_dopad:N", title="predikovaný dopad"), alt.Tooltip("skutočný:N", title="skutočný dopad"),
               alt.Tooltip("strata text:N", title="očakávaná strata"), alt.Tooltip("opatrenie:N")]
    line = alt.Chart(data).mark_line(color=RESIDUAL_COLOR, strokeWidth=1.2, opacity=0.7).encode(x=x, y=y)
    points = alt.Chart(data).mark_circle(size=120, opacity=0.95, stroke="white", strokeWidth=0.8).encode(
        x=x, y=y, color=color, tooltip=tooltip)
    return finish((line + points).properties(height=300))


def live_patterns_chart(frame, top=8):
    """Vzory útokov v posledných incidentoch, rozdelené podľa predikovaného dopadu."""
    order = frame["vzor_utoku"].value_counts().head(top).index.tolist()
    data = (frame[frame["vzor_utoku"].isin(order)].groupby(["vzor_utoku", "predikovany_dopad"])
            .size().rename("počet").reset_index())
    y = alt.Y("vzor_utoku:N", sort=order, title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=260, labelPadding=8))
    bars = alt.Chart(data).mark_bar(height=22).encode(
        y=y,
        x=alt.X("počet:Q", stack="zero", title=None, axis=alt.Axis(format="d", tickMinStep=1, grid=False)),
        color=alt.Color("predikovany_dopad:N", sort=op.LABELS,
                        scale=alt.Scale(domain=list(IMPACT_COLORS), range=list(IMPACT_COLORS.values())), legend=None),
        order=alt.Order("poradie:Q"),
        tooltip=[alt.Tooltip("vzor_utoku:N", title="vzor útoku"), alt.Tooltip("predikovany_dopad:N", title="dopad"),
                 alt.Tooltip("počet:Q", title="počet")],
    ).transform_calculate(poradie="indexof(['nízky', 'stredný', 'vysoký'], datum.predikovany_dopad)")
    return finish(bars.properties(height=40 * len(order)))


def live_feed_html(frame, seen):
    """Posledné incidenty ako tabuľka, najnovší hore. Incidenty od posledného obnovenia sú zvýraznené."""
    rows = []
    for _, row in frame.iterrows():
        actual = row["skutocny_dopad"] if isinstance(row["skutocny_dopad"], str) and row["skutocny_dopad"] else None
        verdict = "" if actual is None else (
            '<span class="rk-hit">✓</span>' if actual == row["predikovany_dopad"] else '<span class="rk-miss">✗</span>')
        rows.append(
            f'<tr class="{"new" if row["id"] > seen else ""}">'
            f'<td class="num">{esc(row["čas"].strftime("%H:%M:%S"))}</td>'
            f'<td>{esc(row["nazov"] or f"#{row.id}")}</td><td>{esc(row["odvetvie"])}</td><td>{esc(row["vzor_utoku"])}</td>'
            f'<td>{impact_pill(row["predikovany_dopad"], small=True)}</td>'
            f'<td>{impact_pill(actual, small=True) + " " + verdict if actual else "–"}</td>'
            f'<td class="num">{esc(euro(row["ocakavana_strata"]))}</td><td>{esc(row["opatrenie"])}</td></tr>'
        )
    return ('<div class="rk-feed"><table><thead><tr><th>Čas</th><th>Incident</th><th>Odvetvie</th><th>Vzor útoku</th>'
            '<th>Predikovaný dopad</th><th>Skutočný dopad</th><th class="num">Strata / rok</th><th>Opatrenie</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


@st.fragment(run_every=LIVE_REFRESH)
def live_tab():
    """Incidenty, ktoré posiela generátor simulacia.py cez API, zobrazené naživo."""
    top = st.columns([3, 1.3, 1], vertical_alignment="center")
    scope = top[1].segmented_control("Zdroj", ["Iba simulácia", "Všetky zdroje"], default="Iba simulácia",
                                     key="live_scope", label_visibility="collapsed")
    records = op.load_assessments()
    simulated = records[records["zdroj"] == LIVE_SOURCE]
    shown = records if scope == "Všetky zdroje" else simulated

    with top[2].popover("Vymazať simuláciu", icon=":material/delete:", disabled=simulated.empty, width="stretch"):
        st.write(f"Vymaže {len(simulated)} hodnotení zo simulácie. Ostatné hodnotenia zostanú.")
        if st.button("Vymazať", type="primary", key="live_delete"):
            op.delete_assessments(simulated["id"].tolist())
            st.session_state.pop("live_seen", None)
            st.rerun(scope="fragment")

    now = datetime.now()
    times = pd.to_datetime(simulated["vytvorene"], errors="coerce")
    idle = (now - times.max()).total_seconds() if len(times) else None
    if idle is not None and idle <= LIVE_IDLE:
        top[0].html('<div class="rk-live on"><span class="rk-dot"></span><b>Generátor beží</b> · posledný incident '
                    f'pred {int(idle)} s</div>')
    else:
        since = f" · posledný incident {esc(date_time(simulated['vytvorene'].iloc[times.argmax()]))}" if len(times) else ""
        top[0].html('<div class="rk-live"><span class="rk-dot"></span><b>Generátor nebeží</b>'
                    f'{since} · spustite <code>python simulacia.py</code></div>')

    if shown.empty:
        st.html(f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Čakám na incidenty</h4>'
                '<p>Spustite API (<code>uvicorn api:app --port 8000</code>) a generátor (<code>python simulacia.py</code>). '
                'Každých pár sekúnd pošle testovací incident z VCDB, ktorý sa tu hneď objaví.</p></div>')
        return

    frame = shown.assign(čas=pd.to_datetime(shown["vytvorene"], errors="coerce")).dropna(subset=["čas"])
    frame = frame.sort_values("id").tail(LIVE_WINDOW)
    last_minute = int((pd.to_datetime(shown["vytvorene"], errors="coerce") >= now - pd.Timedelta(minutes=1)).sum())
    known = shown[shown["skutocny_dopad"].isin(op.LABELS)]
    accuracy = percent((known["skutocny_dopad"] == known["predikovany_dopad"]).mean()) if len(known) else "–"
    high = int((shown["predikovany_dopad"] == "vysoký").sum())
    st.html(kpi_row([
        ("Incidenty", str(len(shown)), f"{last_minute} za poslednú minútu"),
        ("Vysoký dopad", str(high), f"{percent(high / len(shown))} incidentov"),
        ("Zhoda so skutočným dopadom", accuracy, f"z {len(known)} incidentov so známym dopadom"),
        ("Očakávaná strata spolu", euro(shown["ocakavana_strata"].sum()),
         f"ročne, po opatreniach {esc(euro(shown['zostavajuca_strata'].sum()))}"),
    ]))

    seen = st.session_state.get("live_seen", int(frame["id"].max()))
    st.html(f'<div class="rk-section">Posledné incidenty</div>'
            f'{live_feed_html(frame.sort_values("id", ascending=False).head(LIVE_FEED), seen)}')
    st.session_state["live_seen"] = int(frame["id"].max())

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.html(f'<div class="rk-section">Očakávaná ročná strata posledných {len(frame)} incidentov</div>')
        st.altair_chart(live_loss_chart(frame), width="stretch")
    with right:
        st.html(f'<div class="rk-section">Vzory útokov v posledných {len(frame)} incidentoch</div>')
        st.altair_chart(live_patterns_chart(frame), width="stretch")
    st.caption(f"Záložka sa obnovuje každé {LIVE_REFRESH} s. Incidenty posiela generátor simulacia.py na POST /api/hodnotenie; "
               "skutočný dopad je známy z dát VCDB a model ho pri predikcii nepoužíva.")


def register_tab():
    register = op.load_register()
    worthwhile = register[register["opatrenie"] != op.OPTION_NAMES[0]]
    st.html(kpi_row([
        ("Scenáre s opatrením", f"{len(worthwhile)} z {len(register)}", "6 odvetví × 8 vzorov útokov"),
        ("Cena odporúčaných opatrení", euro(worthwhile["cena opatrenia (€)"].sum() - op.MONITORING_COST * len(worthwhile)),
         "ročne, bez monitorovania"),
        ("Čistý prínos spolu", euro(register["čistý prínos (€)"].sum()), "ročne oproti nečinnosti"),
    ]))

    st.html('<div class="rk-section">Mapa rizík</div><div class="rk-note">Farba je odporúčané opatrenie, číslo očakávaná '
            'ročná strata scenára. Podrobnosti ukáže kurzor nad bunkou.</div>')
    st.altair_chart(register_chart(register), width="stretch")

    st.html('<div class="rk-section">Register rizík</div><div class="rk-note">Priorita je poradie zavádzania podľa čistého '
            'prínosu na každé investované euro. Scenáre bez opatrenia nemajú prioritu.</div>')
    sectors = st.pills("Odvetvie", list(dict.fromkeys(register["odvetvie"])), selection_mode="multi",
                       label_visibility="collapsed")
    shown = (register[register["odvetvie"].isin(sectors)] if sectors else register).copy()
    # Streamlit pri prázdnej číselnej bunke ignoruje formát a vypíše None, preto je priorita text
    shown["priorita"] = shown["priorita"].map(lambda value: "–" if pd.isna(value) else f"{value:.0f}")
    money = {column: euro for column in ["očakávaná strata (€)", "cena opatrenia (€)", "zostávajúca strata (€)", "čistý prínos (€)"]}
    styled = shown.style.format({
        **money,
        "frekvencia za rok": lambda value: decimal(value),
        "P(vysoký dopad)": percent,
    })
    st.dataframe(
        styled, hide_index=True, width="stretch", height=420,
        column_order=[
            "priorita", "odvetvie", "vzor_utoku", "frekvencia za rok", "P(vysoký dopad)", "očakávaná strata (€)",
            "opatrenie", "opatrenia CIS", "cena opatrenia (€)", "zostávajúca strata (€)", "čistý prínos (€)",
            "odhad dopadu z", "incidenty v odhade",
        ],
        column_config={
            "priorita": st.column_config.TextColumn("Priorita", width="small", alignment="right"),
            "odvetvie": "Odvetvie", "vzor_utoku": "Vzor útoku", "frekvencia za rok": "Frekvencia za rok",
            "očakávaná strata (€)": "Očakávaná strata", "opatrenie": "Opatrenie", "opatrenia CIS": "Opatrenia CIS",
            "cena opatrenia (€)": "Cena opatrenia", "zostávajúca strata (€)": "Zostávajúca strata",
            "čistý prínos (€)": "Čistý prínos", "odhad dopadu z": "Odhad dopadu z", "incidenty v odhade": "Incidenty v odhade",
        },
    )

    budget_section()
    strategy_section()


def budget_section():
    total = op.budget_total()
    st.html('<div class="rk-section">Priorita pri obmedzenom rozpočte</div><div class="rk-note">Opatrenia sa zavádzajú '
            f'postupne, kým stačí ročný rozpočet. Všetky odporúčané opatrenia stoja {euro(total)} ročne. Znížená strata '
            'je spočítaná pri skutočnom dopade testovacích incidentov.</div>')
    steps = sorted(set(range(0, int(total) + 1, 10_000)) | {int(total)})
    budget = st.select_slider("Ročný rozpočet na opatrenia", steps, value=min(250_000, int(total)), format_func=euro,
                              key="rozpocet")
    curves = op.budget_curves()
    covered, reduced = op.budget_coverage(budget, op.BUDGET_ORDERS[0])
    covered_freq, reduced_freq = op.budget_coverage(budget, op.BUDGET_ORDERS[1])
    spent = covered["cena (€)"].sum()
    st.html(kpi_row([
        ("Pokryté scenáre", f"{len(covered)} z {len(curves[op.BUDGET_ORDERS[0]])}", f"minie sa {esc(euro(spent))}"),
        ("Znížená strata podľa prínosu na euro", euro(reduced), "ročne"),
        ("Znížená strata podľa frekvencie", euro(reduced_freq),
         f"{len(covered_freq)} scenárov, o {esc(euro(reduced - reduced_freq))} menej" if reduced >= reduced_freq
         else f"{len(covered_freq)} scenárov"),
    ]))
    st.altair_chart(budget_chart(curves, budget), width="stretch")
    if covered.empty:
        st.caption("Z tohto rozpočtu sa nepokryje žiadny scenár. Najlacnejšie prvé opatrenie stojí "
                   f"{euro(curves[op.BUDGET_ORDERS[0]]['cena (€)'].iloc[0])}.")
        return
    with st.expander(f"Scenáre pokryté z rozpočtu {euro(budget)} ({len(covered)})", icon=":material/checklist:"):
        st.dataframe(
            covered.style.format({"cena (€)": euro, "znížená strata (€)": euro, "rozpočet (€)": euro}),
            hide_index=True, width="stretch",
            column_order=["poradie", "odvetvie", "vzor_utoku", "opatrenie", "opatrenia CIS", "cena (€)",
                          "znížená strata (€)", "rozpočet (€)"],
            column_config={"poradie": st.column_config.NumberColumn("Poradie", width="small"), "odvetvie": "Odvetvie",
                           "vzor_utoku": "Vzor útoku", "opatrenie": "Opatrenie", "opatrenia CIS": "Opatrenia CIS",
                           "cena (€)": "Ročná cena", "znížená strata (€)": "Znížená strata",
                           "rozpočet (€)": "Rozpočet spolu"},
        )


def strategy_section():
    strategies = op.strategy_comparison()
    ours = strategies[strategies["naša"]].iloc[0]
    best = strategies.iloc[0]
    fixed = strategies[strategies["stratégia"].str.startswith("Všade")].iloc[0]
    st.html('<div class="rk-section">Porovnanie stratégií</div><div class="rk-note">Priemerné ročné náklady na organizáciu '
            'pri skutočnom dopade testovacích incidentov: cena opatrení plus strata, ktorá zostane. Nižšie je lepšie.</div>')
    st.html(kpi_row([
        ("Naše riešenie", euro(ours["na organizáciu (€)"]), "ročne na organizáciu"),
        ("Rozdiel od optima", euro(ours["na organizáciu (€)"] - best["na organizáciu (€)"]), esc(best["stratégia"])),
        ("Úspora oproti najlepšej pevnej",
         decimal((fixed["na organizáciu (€)"] - ours["na organizáciu (€)"]) / fixed["na organizáciu (€)"] * 100, 1) + " %",
         esc(fixed["stratégia"].lower())),
    ]))
    st.altair_chart(strategy_chart(strategies), width="stretch")


def assumptions_tab():
    st.warning(
        "Dataset neobsahuje ceny ani účinnosť opatrení. Hodnoty nižšie sú predpoklady pre modelovú organizáciu "
        "z notebooku preskriptivna_udrzba.ipynb a pri skutočnom použití ich treba nahradiť údajmi organizácie.",
        icon=":material/info:",
    )
    st.html(kpi_row([
        ("Horizont", f"{op.HORIZON_YEARS} roky", "opatrenie chráni len po zavedení"),
        ("Závažné incidenty za rok", decimal(op.INCIDENTS_PER_YEAR, 1), "rozdelené podľa podielu vzoru v odvetví"),
        ("Monitorovanie", euro(op.MONITORING_COST), "ročne, vždy"),
    ]))

    left, right = st.columns(2, gap="large")
    with left:
        st.html('<div class="rk-section">Strata z jedného incidentu podľa dopadu</div>')
        loss = op.LOSS.rename("strata").to_frame()
        st.dataframe(loss.style.format({"strata": euro}), width="stretch",
                     column_config={"_index": "Dopad", "strata": "Strata z incidentu"})
    with right:
        st.html('<div class="rk-section">Ročná cena jedného opatrenia CIS podľa typu</div>')
        cost = pd.Series(op.CONTROL_COST, name="cena").to_frame()
        st.dataframe(cost.style.format({"cena": euro}), width="stretch",
                     column_config={"_index": "Typ opatrenia", "cena": "Ročná cena"})

    st.html('<div class="rk-section">Typy opatrení</div>')
    options = op.OPTIONS.copy()
    options["chráni časť horizontu"] = (12 * op.HORIZON_YEARS - op.OPTIONS["mesiace zavedenia"]) / (12 * op.HORIZON_YEARS)
    st.dataframe(
        options.style.format({"menej incidentov": percent, "menšia strata": percent, "chráni časť horizontu": percent,
                              "mesiace zavedenia": lambda value: f"{value:.0f}"}),
        width="stretch",
        column_config={"_index": "Opatrenie", "menej incidentov": "Menej incidentov", "menšia strata": "Menšia strata",
                       "mesiace zavedenia": "Mesiace zavedenia", "chráni časť horizontu": "Chráni časť horizontu"},
    )

    st.html('<div class="rk-section">Výpočet</div>')
    st.code(
        "očakávaná strata = frekvencia × Σ P(dopad) × strata(dopad)\n"
        "celkové náklady(a) = cena(a) + očakávaná strata × (1 − menej_incidentov(a) × f) × (1 − menšia_strata(a) × f)\n"
        "f = (36 − mesiace_zavedenia(a)) / 36\n"
        "odporúčané opatrenie = to s najnižšími celkovými nákladmi",
        language=None,
    )

    st.html('<div class="rk-section">Ročná cena opatrení podľa vzoru útoku</div>')
    costs = op.cost_table()
    money = [column for column in costs.columns if column.endswith("(€)")]
    st.dataframe(costs.style.format({column: euro for column in money}), hide_index=True, width="stretch",
                 column_config={**{column: column.replace(" (€)", "") for column in money},
                                "vzor útoku": "Vzor útoku", "prevencia": "CIS: prevencia",
                                "detekcia a reakcia": "CIS: detekcia a reakcia"})

    st.html('<div class="rk-section">Prahy: od akej očakávanej ročnej straty sa opatrenie oplatí</div>')
    thresholds = op.thresholds()
    money = [column for column in thresholds.columns if column.endswith("(€)")]
    st.dataframe(
        thresholds.style.format({column: euro for column in money}, na_rep="–"),
        hide_index=True, width="stretch",
        column_config={column: column.replace(" (€)", "").capitalize() for column in thresholds.columns},
    )
    st.caption("Pomlčka znamená, že pri tomto vzore je vždy výhodnejšie iné opatrenie.")


# ---------------------------------------------------------------- stránka

st.html(CSS.replace("SHIELD_SVG", SHIELD_SVG))
st.html(
    f'<div class="rk-header"><div class="rk-logo">{SHIELD}</div><div>'
    '<div class="rk-title">Hodnotenie rizika bezpečnostných incidentov</div>'
    '<div class="rk-subtitle">Zadajte incident tak, ako ho poznáte hneď po odhalení. Model odhadne jeho dopad '
    'a aplikácia odporučí opatrenie podľa rizika, nákladov a času zavedenia.</div>'
    '<div class="rk-chips"><span class="rk-chip">VCDB · VERIS</span><span class="rk-chip">LightGBM</span>'
    '<span class="rk-chip">CIS Controls v8</span></div></div></div>'
)

missing = op.missing_files()
if missing:
    st.error(f"Chýbajú súbory {', '.join(path.name for path in missing)}. Najprv spustite notebooky podľa README.md.")
    st.stop()

load_context()

tab_new, tab_records, tab_overview, tab_live, tab_register, tab_assumptions = st.tabs(
    ["Nové hodnotenie", "Uložené hodnotenia", "Prehľad", "Živé sledovanie", "Register rizík", "Predpoklady"]
)
with tab_new:
    new_assessment_tab()
with tab_records:
    records_tab()
with tab_overview:
    overview_tab()
with tab_live:
    live_tab()
with tab_register:
    register_tab()
with tab_assumptions:
    assumptions_tab()
