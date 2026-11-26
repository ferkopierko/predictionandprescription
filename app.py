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
import frontend as ui
import firma as co
import firma_ui as company_ui

st.set_page_config(page_title="safetyfirst", page_icon="◈", layout="wide", initial_sidebar_state="auto")

PREFIX = "f_"
SELECT_FIELDS = ["odvetvie", "velkost_organizacie", "krajina", "cielenost"]
LIST_FIELDS = ["aktor_typy", "akcia_typy", *op.DETAIL_COLUMNS]
CHECK_FIELDS = ["atribut_integrity", "atribut_availability"]
REQUIRED_SELECTS = ["odvetvie", "velkost_organizacie"]

# Farby dopadu a opatrení sú rovnaké v rozhraní aj vo všetkých grafoch.
IMPACT_COLORS = {"nízky": "#287A62", "stredný": "#B87926", "vysoký": "#BE514A"}
IMPACT_CLASS = {"nízky": "low", "stredný": "mid", "vysoký": "high"}
OPTION_COLORS = dict(zip(op.OPTION_NAMES, ["#8A9EAA", "#087F8C", "#6A6C98", "#29546D"]))
COST_COLOR = "#087F8C"
RESIDUAL_COLOR = "#BACBD4"
LABEL_COLOR = "#526B7B"
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

SHIELD = '<span class="rk-shield" aria-hidden="true"></span>'


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
        date = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return f"{date.day}. {date.month}. {date.year} {date:%H:%M}"
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
    values = {field: list(value or []) if field in LIST_FIELDS else value for field, value in values.items()}
    values.update(odvetvie="Výroba", velkost_organizacie="malá", krajina="iná")
    asset_id = st.session_state.get("company_asset")
    if asset_id:
        values["aktivum_variety"] = [co.asset(asset_id)["model_asset"]]
    return values


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
    values.update(odvetvie="Výroba", velkost_organizacie="malá", krajina="iná")
    return values


def init_form():
    if PREFIX + "krajina" not in st.session_state:
        set_form(empty_form())


def start_company_scenario(scenario_id, finding_id=None):
    case = co.start_simulation(scenario_id, finding_id)
    set_form(case["input"])
    st.session_state.update(company_asset=case["asset_id"], company_finding=case["finding_id"],
                            simulation=case, workspace_page="Nové hodnotenie", intake_step=1, scroll_to_step=True)
    st.session_state[PREFIX + "nazov"] = case["title"]
    for key in ["demo", "vysledok", "chyby"]:
        st.session_state.pop(key, None)


def start_manual_asset(asset_id):
    set_form(co.incident_input(asset_id))
    st.session_state.update(company_asset=asset_id, company_finding=None, workspace_page="Nové hodnotenie", intake_step=1, scroll_to_step=True)
    st.session_state[PREFIX + "nazov"] = ""
    for key in ["simulation", "demo", "vysledok", "chyby"]:
        st.session_state.pop(key, None)


def fill_random_incident():
    available = co.findings()
    available = available[available.status != "Odstránená"]
    if available.empty:
        st.session_state["chyby"] = ["Nie sú k dispozícii otvorené zistenia pre simuláciu."]
        return
    finding = available.iloc[0]
    start_company_scenario(finding.scenario, finding.id)


def select_company_asset():
    selected = st.session_state.get("company_asset")
    set_form(co.incident_input(selected) if selected else empty_form())
    st.session_state["company_finding"] = None
    for key in ["simulation", "demo", "vysledok", "chyby"]:
        st.session_state.pop(key, None)


def clear_form():
    set_form(empty_form())
    for key in ["demo", "vysledok", "chyby", "simulation"]:
        st.session_state.pop(key, None)
    st.session_state["company_asset"] = None
    st.session_state["company_finding"] = None
    st.session_state[PREFIX + "nazov"] = ""
    st.session_state["intake_step"] = 0
    st.session_state["scroll_to_step"] = True


def forget_demo():
    """Invalidate the previous assessment after editing incident characteristics."""
    st.session_state.pop("demo", None)
    st.session_state.pop("vysledok", None)
    st.session_state.pop("chyby", None)


def required_errors(values):
    errors = []
    if not st.session_state.get("company_asset"):
        errors.append("Vyberte dotknuté firemné aktívum.")
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
    simulation = st.session_state.get("simulation")
    asset_id = st.session_state["company_asset"]
    finding_id = st.session_state.get("company_finding")
    case_id = simulation["id"] if simulation and simulation["asset_id"] == asset_id and simulation["finding_id"] == finding_id else None
    try:
        record_id, result = co.assess_and_save(values, asset_id, frequency, st.session_state.get(PREFIX + "nazov", ""), finding_id, case_id)
    except ValueError as error:
        st.session_state["chyby"] = [str(error)]
        return
    st.session_state["vysledok"] = (record_id, result, None, st.session_state.get(PREFIX + "nazov", ""))
    st.session_state["scroll_to_step"] = True


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
                   "Pri zadaných predpokladoch ostatné možnosti vychádzajú drahšie.")
    else:
        savings = (f"Opatrenie stojí <b>{euro(result['cena_opatrenia'])}</b> ročne, znižuje očakávanú stratu na "
                   f"<b>{euro(result['zostavajuca_strata'])}</b> a modelový čistý prínos oproti monitorovaniu je "
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
    if result.get("asset_name"):
        st.caption(f"Firma: {result['company']} · Aktívum: {result['asset_name']} · Incident: {result.get('case_id') or 'ručné hodnotenie'}")
        if not result.get("within_budget", True):
            st.warning("Ekonomicky najvýhodnejšie opatrenie presahuje ročný rozpočet firmy. Porovnajte dostupné možnosti v registri rizík.")
        if result.get("finding_id"):
            finding = co.finding(result["finding_id"])
            st.info(f"Konkrétna oprava {finding['id']}: {finding['remediation']} Odhad jednorazovej ceny: {euro(finding['cost'])}.")
            st.button("Otvoriť súvisiacu zraniteľnosť", icon=":material/build:", on_click=open_linked_finding, args=(finding["id"],))


    st.html('<div class="rk-section">Pravdepodobnosť dopadu</div>')
    actual = demo["skutocny_dopad"] if demo else None
    probabilities = "".join(
        f'<div class="atlas-probability-row"><div><span>{esc(label.capitalize())}</span>'
        f'{"<small>Skutočný dopad</small>" if label == actual else ""}'
        f'<strong>{percent(value)}</strong></div>'
        f'<div class="atlas-probability-track" role="meter" aria-label="Pravdepodobnosť: {esc(label)}" '
        f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{value * 100:.2f}">'
        f'<i style="width:{value * 100:.3f}%;background:{IMPACT_COLORS[label]}"></i></div></div>'
        for label, value in result["pravdepodobnosti"].items()
    )
    st.html(f'<div class="atlas-probabilities">{probabilities}</div>')

    st.html('<div class="rk-section">Ročné náklady podľa opatrenia</div>'
            '<div class="rk-note"><b style="color:#087F8C">■</b> cena opatrenia + <b style="color:#BACBD4">■</b> strata, ktorá '
            'zostane. Zaškrtnutie označuje najvýhodnejšiu možnosť.</div>')
    maximum = max(item["celkove_naklady"] for item in result["porovnanie"])
    cost_rows = "".join(
        f'<div class="atlas-cost-row {"is-recommended" if item["odporucane"] else ""}">'
        f'<div><span>{"✓ " if item["odporucane"] else ""}{esc(item["opatrenie"])}</span>'
        f'<strong>{euro(item["celkove_naklady"])}</strong></div>'
        f'<div class="atlas-cost-track" aria-hidden="true">'
        f'<i style="width:{100 * item["cena"] / maximum:.3f}%;background:{COST_COLOR}"></i>'
        f'<i style="width:{100 * item["zostavajuca_strata"] / maximum:.3f}%;background:{RESIDUAL_COLOR}"></i>'
        '</div></div>'
        for item in result["porovnanie"]
    )
    st.html(f'<div class="atlas-cost-comparison">{cost_rows}</div>')

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
    st.caption("Sumy vychádzajú z modelových predpokladov uvedených v časti Predpoklady. Výsledok je prvotné posúdenie a nenahrádza analytika.")


def open_linked_finding(finding_id):
    st.session_state.update(workspace_page="Firma", company_view="Zraniteľnosti", company_finding_detail=finding_id)


def empty_result():
    values = form_values()
    fields = [
        ("Aktívum", co.asset(st.session_state["company_asset"])["name"] if st.session_state.get("company_asset") else None),
        ("Aktér", ", ".join(pr.label("aktor_typy", item) for item in values["aktor_typy"])),
        ("Typ útoku", ", ".join(pr.label("akcia_typy", item) for item in values["akcia_typy"])),
    ]
    completed = sum(bool(value) for _, value in fields)
    rows = "".join(
        f'<div class="atlas-summary-row"><span>{esc(label)}</span>'
        f'<strong class="{"is-filled" if value else "is-missing"}">{esc(value if value else "Zatiaľ nevyplnené")}</strong></div>'
        for label, value in fields
    )
    pattern = ""
    if values["aktor_typy"] and values["akcia_typy"]:
        pattern = f'<div class="atlas-pattern"><span>Rozpoznaný vzor</span><strong>{esc(op.to_row(model_input(values))["vzor_utoku"])}</strong></div>'
    st.html(
        f'<section class="atlas-empty-report"><h3>Váš incident</h3>'
        f'<p class="atlas-progress-label">{completed} z 3 povinných údajov</p>'
        f'<div class="atlas-readiness-track" role="meter" aria-label="Vyplnené povinné údaje" '
        f'aria-valuemin="0" aria-valuemax="3" aria-valuenow="{completed}"><i style="width:{completed * 100 / 3}%"></i></div>'
        f'<div class="atlas-summary">{rows}</div>{pattern}'
        '<div class="atlas-report-explanation"><strong>Výsledok hodnotenia</strong>'
        '<p>Odhad rozsahu úniku dát, porovnanie štyroch možností ochrany a odporúčanie s vysvetlením nákladov.</p></div></section>'
    )


# ---------------------------------------------------------------- záložky

def detail_select(column, field, options):
    column.multiselect(
        op.FIELD_NAMES[field].capitalize(), options[field], key=PREFIX + field, help=HELP[field],
        placeholder="Vyberte", format_func=pr.formatter(field), on_change=forget_demo,
    )


def change_intake_step(target):
    st.session_state["intake_step"] = target
    st.session_state.pop("chyby", None)
    st.session_state["scroll_to_step"] = True


def incident_form(options):
    values = form_values()
    complete = [bool(st.session_state.get("company_asset")),
                bool(values["aktor_typy"] and values["akcia_typy"]), "vysledok" in st.session_state]
    current = st.session_state.get("intake_step", 0)
    names = ["Aktívum", "Incident", "Vyhodnotenie"]
    with st.container(key="wizard_navigation"):
        stage = st.segmented_control(
            "Postup hodnotenia", [0, 1, 2], default=0 if "intake_step" not in st.session_state else None,
            key="intake_step", width="stretch",
            format_func=lambda value: f'{"✓" if complete[value] and value != current else str(value + 1) + "."} {names[value]}',
            label_visibility="collapsed", on_change=scroll_to_current_step,
        )
    stage = 0 if stage is None else stage
    instructions = [
        ("Aktívum firmy", "Vyberte firemné aktívum, ktorého sa incident týka. Profil organizácie je už nastavený."),
        ("Incident", "Označte, kto incident spôsobil a čo sa stalo. Potom pokračujte k vyhodnoteniu."),
        ("Vyhodnotenie", "Frekvenciu môžete ponechať predvyplnenú. Tlačidlo Vyhodnotiť a uložiť zobrazí výsledok."),
    ]
    title, instruction = instructions[stage]
    st.html(f'<div class="atlas-step-guide stage-{stage}"><span class="atlas-step-number">{stage + 1}</span>'
            f'<div><strong>Krok {stage + 1} z 3: {title}</strong><p>{instruction}</p></div></div>')
    with st.expander("Ukážkový incident alebo nový formulár", icon=":material/science:"):
        st.caption("Ukážka vytvorí simulovaný incident z otvorenej zraniteľnosti firmy HronTech.")
        buttons = st.columns([1, 1])
        buttons[0].button("Načítať ukážku", icon=":material/science:", on_click=fill_random_incident, width="stretch")
        buttons[1].button("Začať odznova", icon=":material/restart_alt:", on_click=clear_form, width="stretch")
    simulation = st.session_state.get("simulation")
    if simulation:
        st.html(f'<div class="rk-demo"><span class="atlas-demo-dot"></span><div><b>Simulovaný incident č. {simulation["id"]}: {esc(simulation["title"])}</b><br>{esc(simulation["description"])}</div></div>')

    with st.container(key="incident_basics"):
        if stage == 0:
            profile = co.profile()
            st.html('<div class="atlas-form-heading"><h2>Dotknuté aktívum firmy</h2>'
                    '<p>Hodnotenie sa týka výrobnej firmy HronTech. Odvetvie a veľkosť sa dopĺňajú automaticky.</p></div>')
            st.caption(f"{profile['name']} · {profile['employees']} zamestnancov · Slovensko")
            inventory = co.assets()
            st.selectbox("Firemné aktívum", inventory.id.tolist(), index=None, key="company_asset",
                         placeholder="Vyberte počítač, server alebo web", format_func=lambda value: f"{value} · {co.asset(value)['name']}", on_change=select_company_asset)
            selected = st.session_state.get("company_asset")
            if selected:
                asset = co.asset(selected)
                st.html(f'<div class="atlas-pattern"><span>{esc(asset["category"])} · {esc(asset["address"])}</span><strong>{esc(asset["technology"])}</strong></div>')
                findings = co.findings()
                candidates = findings[(findings.asset_id == selected) & (findings.status != "Odstránená")]
                if st.session_state.get("company_finding") not in candidates.id.tolist():
                    st.session_state["company_finding"] = None
                st.selectbox("Súvisiaca zraniteľnosť (nepovinné)", candidates.id.tolist(), index=None, key="company_finding",
                             format_func=lambda value: f"{value} · {co.finding(value)['title']}", placeholder="Vyberte zistenie z evidencie", on_change=forget_demo)
            st.button("Pokračovať k incidentu", type="primary", icon=":material/arrow_forward:", width="stretch",
                      on_click=change_intake_step, args=(1,))

        elif stage == 1:
            st.html('<div class="atlas-form-heading"><h2>Údaje o incidente</h2>'
                    '<p>Vyberte aktéra a spôsob útoku. Môžete označiť viac možností.</p></div>')
            st.pills("Kto incident spôsobil?", options["aktor_typy"], selection_mode="multi", key=PREFIX + "aktor_typy",
                     format_func=pr.formatter("aktor_typy"), help=HELP["aktor_typy"], on_change=forget_demo)
            st.html('<div class="atlas-field-divider"></div>')
            st.pills("Akým spôsobom incident vznikol?", options["akcia_typy"], selection_mode="multi", key=PREFIX + "akcia_typy",
                     format_func=pr.formatter("akcia_typy"), help=HELP["akcia_typy"], on_change=forget_demo)
            with st.expander("Doplniť podrobnosti incidentu", icon=":material/tune:"):
                st.caption("Zadajte iba overené údaje. Neznáme informácie nechajte prázdne.")
                st.segmented_control("Cielenosť útoku", options["cielenost"], key=PREFIX + "cielenost",
                                     format_func=str.capitalize, on_change=forget_demo, width="stretch")
                for field in ["aktor_variety", "akcia_variety", "akcia_vektory", "typy_dat", "motiv", "sposob_odhalenia"]:
                    detail_select(st, field, options)
                st.toggle("Narušená integrita", key=PREFIX + "atribut_integrity", on_change=forget_demo,
                          help="Údaje alebo systém boli zmenené.")
                st.toggle("Narušená dostupnosť", key=PREFIX + "atribut_availability", on_change=forget_demo,
                          help="Údaje alebo služba neboli dostupné.")
            back, forward = st.columns([1, 1.8])
            back.button("Späť", icon=":material/arrow_back:", on_click=change_intake_step, args=(0,), width="stretch")
            forward.button("Pokračovať k vyhodnoteniu", type="primary", icon=":material/arrow_forward:",
                           on_click=change_intake_step, args=(2,), width="stretch")

        else:
            st.html('<div class="atlas-form-heading"><h2>Nastavenie hodnotenia</h2>'
                    '<p>Nastavte ročnú frekvenciu podobných incidentov. Názov je nepovinný.</p></div>')
            row = op.to_row(model_input(form_values()))
            pair = (row["odvetvie"], row["vzor_utoku"])
            default = simulation["frequency"] if simulation else op.default_frequency(*pair)
            if st.session_state.get("frekvencia_pre") != pair:
                st.session_state["frekvencia"] = decimal(default, 4)
                st.session_state["frekvencia_pre"] = pair
            st.html(f'<div class="atlas-pattern"><span>Scenár podľa zadaných údajov</span><strong>{esc(row["vzor_utoku"])}</strong></div>')
            st.text_input("Ročná frekvencia podobných incidentov", key="frekvencia", on_change=forget_demo,
                          help="Predvolená hodnota vychádza z podielu vzoru v odvetví pri jednom závažnom incidente ročne. Napríklad 0,2 znamená jeden podobný incident za päť rokov.")
            st.caption(f"Predvolený odhad pre toto odvetvie je {decimal(default)} incidentu ročne. Hodnotu môžete upraviť.")
            st.text_input("Názov hodnotenia", key=PREFIX + "nazov", max_chars=200,
                          placeholder="Napríklad Neoprávnený prístup do e-shopu", help="Nepovinné. Pomôže vám nájsť výsledok v histórii.")
            st.caption("Frekvencia je predpoklad simulácie. Pri ručnom incidente sa predvyplní historický podiel vzoru vo výrobe.")
            with st.container(key="evaluate"):
                st.button("Vyhodnotiť a uložiť", type="primary", icon=":material/shield:", width="stretch", on_click=evaluate)
            st.html('<div class="atlas-form-footnote">Výsledok sa uloží do histórie. Finančný odhad vychádza z modelových predpokladov.</div>')
            for error in st.session_state.get("chyby", []):
                st.error(error, icon=":material/error:")
            st.button("Späť k incidentu", icon=":material/arrow_back:", on_click=change_intake_step, args=(1,))


def new_assessment_tab():
    options = op.choices()
    init_form()
    with st.container(key="assessment_workspace"):
        if "vysledok" in st.session_state:
            st.success("Hodnotenie je dokončené a uložené. Nižšie je odhad dopadu a odporúčané opatrenie.", icon=":material/check_circle:")
            with st.container(key="has_result"):
                show_result(*st.session_state["vysledok"])
            st.button("Upraviť vstupné údaje", icon=":material/edit:", on_click=edit_assessment)
            st.button("Začať odznova", icon=":material/add:", on_click=clear_form)
        else:
            with st.container(key="intake"):
                incident_form(options)
            with st.expander("Skontrolovať zadané údaje", icon=":material/checklist:"):
                empty_result()
    if st.session_state.pop("scroll_to_step", False):
        st.html(
            '<script>requestAnimationFrame(() => document.querySelector(\'[data-testid="stMain"]\')?.scrollTo({top: 0, behavior: "instant"}));</script>',
            unsafe_allow_javascript=True,
        )


def edit_assessment():
    st.session_state.pop("vysledok", None)
    st.session_state["intake_step"] = 0
    st.session_state["scroll_to_step"] = True


def scroll_to_current_step():
    st.session_state["scroll_to_step"] = True


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
    records = co.assessments()
    if records.empty:
        st.html(f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Zatiaľ žiadne hodnotenia</h4>'
                '<p>V časti Nové hodnotenie zadajte incident alebo načítajte ukážku z testovacích dát.</p></div>')
        st.button("Vytvoriť prvé hodnotenie", type="primary", on_click=lambda: st.session_state.update(workspace_page="Nové hodnotenie"))
        return

    search_column, impact_column = st.columns([2.5, 1])
    query = search_column.text_input("Hľadať hodnotenie", placeholder="Názov, odvetvie alebo vzor útoku", key="history_search")
    impact = impact_column.selectbox("Predikovaný dopad", ["Všetky dopady", *op.LABELS], key="history_impact")
    if query.strip():
        searchable = records[["nazov", "odvetvie", "vzor_utoku"]].fillna("").astype(str).agg(" ".join, axis=1)
        records = records[searchable.str.contains(query.strip(), case=False, regex=False)].copy()
    if impact != "Všetky dopady":
        records = records[records["predikovany_dopad"] == impact].copy()
    if records.empty:
        st.info("Žiadne hodnotenie nezodpovedá filtru. Zmeňte hľadaný text alebo vyberte všetky dopady.")
        return

    records.insert(0, "priorita", range(1, len(records) + 1))
    known = records.dropna(subset=["skutocny_dopad"])
    known = known[known["skutocny_dopad"].astype(str).str.len() > 0]
    accuracy = (f"{percent((known['skutocny_dopad'] == known['predikovany_dopad']).mean())}",
                f"z {len(known)} testovacích incidentov") if len(known) else ("–", "žiadne testovacie incidenty")
    st.html(kpi_row([
        ("Uložené hodnotenia", str(len(records)), "uložené vstupy aj výsledky"),
        ("Súčet odhadovaných strát", euro(records["ocakavana_strata"].sum()), "súčet hodnotení, nie riziko celej firmy"),
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
        "priorita", "id", "nazov", "asset_name", "finding_id", "case_id", "vzor_utoku", "opatrenie", "ocakavana_strata",
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
            "nazov": "Názov", "asset_name": "Aktívum", "finding_id": "Zistenie", "case_id": "Incident", "odvetvie": "Odvetvie", "vzor_utoku": "Vzor útoku", "opatrenie": "Opatrenie",
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
                delete_all = st.checkbox("Vymazať všetky zobrazené hodnotenia")
                if st.form_submit_button("Vymazať", icon=":material/delete:"):
                    ids = list(labels) if delete_all else to_delete
                    if ids:
                        op.delete_assessments(ids)
                        st.session_state.pop("vysledok", None)
                        st.rerun()


@st.fragment(run_every=5)
def overview_tab():
    """Grafy z uložených hodnotení. Obnovujú sa každých 5 sekúnd, aby bolo vidieť aj hodnotenia z API."""
    records = co.assessments()
    if records.empty:
        st.html(f'<div class="rk-empty"><div class="rk-empty-icon">{SHIELD}</div><h4>Zatiaľ nie je čo zobraziť</h4>'
                '<p>Grafy sa objavia po prvom hodnotení. Pridajte ho v časti Nové hodnotenie, tlačidlom '
                '<b>Načítať ukážku</b> alebo cez API.</p></div>')
        st.button("Vytvoriť prvé hodnotenie", type="primary", on_click=lambda: st.session_state.update(workspace_page="Nové hodnotenie"))
        return
    timeline = op.assessment_timeline(records)
    last = timeline.iloc[-1]
    top_option = records["opatrenie"].value_counts().idxmax()
    st.html(kpi_row([
        ("Hodnotenia", str(len(records)), f"posledné {esc(date_time(last['vytvorene']))}"),
        ("Súčet odhadovaných strát", euro(records["ocakavana_strata"].sum()), "súčet hodnotení, nie riziko celej firmy"),
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
    left, right = st.columns(2, gap="large")
    with left:
        st.html('<div class="rk-section">Odporúčané opatrenia</div>')
        st.altair_chart(options_chart(records), width="stretch")
    with right:
        st.html('<div class="rk-section">Najčastejšie vzory útokov</div>')
        st.altair_chart(patterns_chart(records), width="stretch")
    st.caption("Súčty vyjadrujú uložené hodnotenia. Prekrývajúce sa scenáre sa môžu započítať opakovane; nejde o celkové riziko firmy.")
    st.caption("Grafy sa obnovujú automaticky každých 5 sekúnd, takže zahŕňajú aj hodnotenia pridané cez API.")


def register_tab():
    register = op.load_register()
    worthwhile = register[register["opatrenie"] != op.OPTION_NAMES[0]]
    st.html(kpi_row([
        ("Scenáre s opatrením", f"{len(worthwhile)} z {len(register)}", "6 odvetví × 8 vzorov útokov"),
        ("Cena odporúčaných opatrení", euro(worthwhile["cena opatrenia (€)"].sum() - op.MONITORING_COST * len(worthwhile)),
         "ročne, bez monitorovania"),
        ("Čistý prínos spolu", euro(register["čistý prínos (€)"].sum()), "ročne oproti nečinnosti"),
    ]))

    view = st.segmented_control(
        "Zobrazenie registra", ["Mapa a scenáre", "Rozpočet", "Stratégie"],
        default="Mapa a scenáre" if "register_view" not in st.session_state else None,
        key="register_view", label_visibility="collapsed", width="stretch",
    )
    if view == "Rozpočet":
        budget_section()
        return
    if view == "Stratégie":
        strategy_section()
        return

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
        "a pri skutočnom použití ich treba nahradiť údajmi organizácie.",
        icon=":material/info:",
    )
    with st.expander("Ako čítať predikciu a odporúčanie", expanded=True):
        st.markdown(
            "**Predikcia dopadu** odhaduje rozsah úniku dát: nízky znamená menej ako 1 000 záznamov, "
            "stredný 1 000 až 99 999 a vysoký aspoň 100 000. Model sa učil z historických incidentov VCDB.\n\n"
            "**Odporúčanie ochrany** porovnáva opatrenia pre podobné budúce incidenty. Zohľadňuje frekvenciu, "
            "modelovú finančnú škodu, cenu ochrany a čas zavedenia. Už vzniknutý únik zavedením prevencie nezmizne."
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

ui.apply_style()
page = ui.shell()
missing = op.missing_files()
if missing:
    st.error(f"Chýbajú súbory {', '.join(path.name for path in missing)}. Najprv spustite notebooky podľa README.md.")
    st.stop()

load_context()
{
    "Firma": lambda: company_ui.company_page(start_company_scenario, start_manual_asset),
    "Simulácia": lambda: company_ui.simulation_page(start_company_scenario),
    "Živé sledovanie": company_ui.live_page,
    "Nové hodnotenie": new_assessment_tab,
    "Uložené hodnotenia": records_tab,
    "Prehľad": overview_tab,
    "Register rizík": company_ui.planning_page,
    "Predpoklady": company_ui.assumptions_page,
}[page]()
ui.footer()
