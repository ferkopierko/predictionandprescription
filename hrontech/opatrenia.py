"""Hodnotenie jedného incidentu VCDB: predikcia dopadu, riziko a výber opatrenia.

Modul používa aplikácia app.py aj REST API api.py. Predpoklady, výpočet nákladov a výber
opatrenia zodpovedajú notebooku preskriptivna_udrzba.ipynb, vzor útoku notebooku priprava_dat.ipynb.
Spustenie `python opatrenia.py` overí, že vstup z formulára dáva rovnaké pravdepodobnosti
ako riadok z vcdb_clean.csv.
"""

import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from hrontech.vcdb_model import CATEGORICAL, FLAGS, LABELS, MULTI, calibrated_probabilities

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CLEAN_PATH = PROCESSED / "vcdb_clean.csv"
PREDICTIONS_PATH = PROCESSED / "vcdb_predikcie.csv"
CONTROLS_PATH = PROCESSED / "vcdb_opatrenia_cis.csv"
REGISTER_PATH = PROCESSED / "vcdb_register_rizik.csv"
MODEL_PATH = PROCESSED / "model_dopad_vcdb.joblib"
FIGURES_DIR = ROOT / "analysis" / "figures"
DB_PATH = Path(os.environ.get("HODNOTENIA_DB", PROCESSED / "hodnotenia.db"))

REQUIRED_FILES = [CLEAN_PATH, PREDICTIONS_PATH, CONTROLS_PATH, REGISTER_PATH, MODEL_PATH]

# Rovnaké hodnoty ako v priprava_dat.ipynb
ACTORS = ["external", "internal", "partner", "unknown"]
ACTIONS = ["hacking", "malware", "social", "error", "misuse", "physical", "environmental", "unknown"]
ASSETS = {
    "S": "server",
    "U": "zariadenie_pouzivatela",
    "M": "nosic_dat",
    "P": "osoba",
    "T": "terminal",
    "N": "sietove_zariadenie",
}
PATTERNS = [
    "Odopretie služby", "Strata a krádež aktív", "Chyby", "Zneužitie oprávnení",
    "Sociálne inžinierstvo", "Útok na webovú aplikáciu", "Prienik do systému", "Ostatné",
]

# Rovnaké predpoklady ako v preskriptivna_udrzba.ipynb
INCIDENTS_PER_YEAR = 1.0
HORIZON_YEARS = 3
LOSS = pd.Series([25_000, 250_000, 2_500_000], index=LABELS, name="strata z incidentu (€)")
CONTROL_COST = {"prevencia": 15_000, "detekcia": 25_000, "obnova": 20_000, "reakcia": 15_000}
MONITORING_COST = 2_000
OPTIONS = pd.DataFrame({
    "menej incidentov": [0.0, 0.40, 0.0, 0.40],
    "menšia strata": [0.0, 0.0, 0.35, 0.35],
    "mesiace zavedenia": [0, 3, 2, 4],
}, index=["Akceptovať a monitorovať", "Prevencia", "Detekcia a reakcia", "Komplexná ochrana"])
OPTION_NAMES = list(OPTIONS.index)

# Hodnota musí byť v dátach aspoň 5-krát, inak ju model nepozná (CountVectorizer min_df=5)
MIN_COUNT = 5
MAJOR_COUNTRIES = ["US", "GB", "CA", "Unknown"]
OTHER_COUNTRY = "iná"
DETAIL_COLUMNS = ["aktor_variety", "akcia_variety", "akcia_vektory", "aktivum_variety", "typy_dat", "motiv", "sposob_odhalenia"]
EMPTY_DEFAULT = {"motiv": "Unknown", "sposob_odhalenia": "unknown"}

FIELD_NAMES = {
    "odvetvie": "odvetvie",
    "velkost_organizacie": "veľkosť organizácie",
    "krajina": "krajina",
    "cielenost": "cielenosť",
    "aktor_typy": "typ aktéra",
    "akcia_typy": "typ útoku",
    "aktor_variety": "podrobný typ aktéra",
    "akcia_variety": "podrobný spôsob útoku",
    "akcia_vektory": "vektor útoku",
    "aktivum_variety": "aktívum",
    "typy_dat": "typ dát",
    "motiv": "motív",
    "sposob_odhalenia": "spôsob odhalenia",
}


def missing_files():
    return [path for path in REQUIRED_FILES if not path.exists()]


# ---------------------------------------------------------------- dáta a model

@lru_cache(maxsize=1)
def context():
    """Načíta dáta, model a možnosti formulára. Výsledok sa načíta iba raz za beh procesu."""
    # Existing local models may reference the module name used before packaging.
    import sys
    from hrontech import vcdb_model
    sys.modules.setdefault("vcdb_model", vcdb_model)
    clean = pd.read_csv(CLEAN_PATH, low_memory=False)
    controls = pd.read_csv(CONTROLS_PATH)
    representative = clean[clean["reprezentativny"]]
    return {
        "bundle": joblib.load(MODEL_PATH),
        "clean": clean,
        "controls": controls,
        "share": pd.crosstab(representative["odvetvie"], representative["vzor_utoku"], normalize="index"),
        "share_all": representative["vzor_utoku"].value_counts(normalize=True),
        "choices": _choices(clean),
    }


def _frequent(values):
    counts = values.value_counts()
    return sorted(counts[counts >= MIN_COUNT].index)


def _frequent_tokens(column):
    tokens = column.fillna("").str.split(";").explode()
    return _frequent(tokens[tokens != ""])


def _choices(clean):
    countries = [country for country in _frequent(clean["krajina"].fillna("Unknown")) if country not in MAJOR_COUNTRIES]
    return {
        "odvetvie": _frequent(clean["odvetvie"]),
        "velkost_organizacie": ["malá", "veľká", "neznáma"],
        "krajina": MAJOR_COUNTRIES + [OTHER_COUNTRY] + countries,
        "cielenost": ["cielený", "príležitostný", "neznáma"],
        "aktor_typy": ACTORS,
        "akcia_typy": ACTIONS,
        **{column: _frequent_tokens(clean[column]) for column in DETAIL_COLUMNS},
    }


def choices():
    """Hodnoty, ktoré formulár a API ponúkajú pre jednotlivé polia."""
    return context()["choices"]


# ---------------------------------------------------------------- vstup

def default_input():
    return {
        "odvetvie": "Neznáme",
        "velkost_organizacie": "neznáma",
        "krajina": "Unknown",
        "cielenost": "neznáma",
        "aktor_typy": [],
        "akcia_typy": [],
        **{column: [] for column in DETAIL_COLUMNS},
        "atribut_integrity": False,
        "atribut_availability": False,
    }


def validate(incident):
    """Vráti zoznam chýb vo vstupe. Prázdny zoznam znamená platný vstup."""
    options = choices()
    errors = []
    for field in ["odvetvie", "velkost_organizacie", "krajina", "cielenost"]:
        if incident.get(field) not in options[field]:
            errors.append(f"Pole {FIELD_NAMES[field]} má neznámu hodnotu {incident.get(field)!r}.")
    for field in ["aktor_typy", "akcia_typy", *DETAIL_COLUMNS]:
        unknown = sorted(set(incident.get(field) or []) - set(options[field]))
        if unknown:
            errors.append(f"Pole {FIELD_NAMES[field]} obsahuje hodnoty, ktoré model nepozná: {', '.join(unknown)}.")
    if not actor_types(incident):
        errors.append("Vyberte aspoň jeden typ aktéra (pri neznámom aktérovi unknown).")
    if not action_types(incident):
        errors.append("Vyberte aspoň jeden typ útoku (pri neznámom spôsobe unknown).")
    return errors


def _with_prefixes(selected, details, names):
    """Typy vybrané priamo a typy, ktoré vyplývajú z podrobných hodnôt, napríklad external:Organized crime."""
    implied = {value.split(":")[0] for value in details}
    return [name for name in names if name in set(selected) | implied]


def actor_types(incident):
    return _with_prefixes(incident.get("aktor_typy") or [], incident.get("aktor_variety") or [], ACTORS)


def action_types(incident):
    return _with_prefixes(
        incident.get("akcia_typy") or [],
        [*(incident.get("akcia_variety") or []), *(incident.get("akcia_vektory") or [])],
        ACTIONS,
    )


def attack_pattern(row):
    """Vzor útoku, rovnaké pravidlá ako attack_pattern v priprava_dat.ipynb."""
    varieties = set(row["akcia_variety"].split(";"))
    vectors = set(row["akcia_vektory"].split(";"))
    if "hacking:DoS" in varieties:
        return "Odopretie služby"
    if "physical:Theft" in varieties or "error:Loss" in varieties:
        return "Strata a krádež aktív"
    if row["akcia_error"]:
        return "Chyby"
    if row["akcia_misuse"]:
        return "Zneužitie oprávnení"
    if row["akcia_social"]:
        return "Sociálne inžinierstvo"
    if "hacking:Web application" in vectors and not row["akcia_malware"]:
        return "Útok na webovú aplikáciu"
    if row["akcia_hacking"] or row["akcia_malware"]:
        return "Prienik do systému"
    return "Ostatné"


def to_row(incident):
    """Prevedie vstup formulára na riadok v tvare vcdb_clean.csv, ktorý očakáva model."""
    def joined(field):
        return ";".join(sorted(set(incident.get(field) or []))) or EMPTY_DEFAULT.get(field, "")

    row = {column: joined(column) for column in DETAIL_COLUMNS}
    country = incident.get("krajina") or "Unknown"
    row.update({
        "odvetvie": incident.get("odvetvie") or "Neznáme",
        "velkost_organizacie": incident.get("velkost_organizacie") or "neznáma",
        # Model rozlišuje iba US, GB, CA a Unknown, ostatné krajiny zlučuje (vcdb_model.prepare)
        "krajina": country,
        "cielenost": incident.get("cielenost") or "neznáma",
    })
    actors, actions = set(actor_types(incident)), set(action_types(incident))
    asset_codes = {value.split(" - ")[0] for value in incident.get("aktivum_variety") or []}
    row.update({f"aktor_{name}": name in actors for name in ACTORS})
    row.update({f"akcia_{name}": name in actions for name in ACTIONS})
    row.update({f"aktivum_{name}": code in asset_codes for code, name in ASSETS.items()})
    row["atribut_integrity"] = bool(incident.get("atribut_integrity"))
    row["atribut_availability"] = bool(incident.get("atribut_availability"))
    row["ransomware"] = "malware:Ransomware" in (incident.get("akcia_variety") or [])
    row["vzor_utoku"] = attack_pattern(row)
    return row


def to_frame(incident):
    columns = MULTI + [column for column in CATEGORICAL if column != "krajina_skupina"] + ["krajina"] + FLAGS
    return pd.DataFrame([to_row(incident)])[columns]


def from_clean_row(row):
    """Prevedie riadok z vcdb_clean.csv na vstup formulára. Ponechá iba hodnoty, ktoré formulár ponúka."""
    options = choices()

    def details(column):
        values = str(row[column]) if pd.notna(row[column]) else ""
        return [value for value in values.split(";") if value in set(options[column])]

    country = row["krajina"] if pd.notna(row["krajina"]) else "Unknown"
    return {
        "odvetvie": row["odvetvie"],
        "velkost_organizacie": row["velkost_organizacie"],
        "krajina": country if country in options["krajina"] else OTHER_COUNTRY,
        "cielenost": row["cielenost"],
        "aktor_typy": [name for name in ACTORS if bool(row[f"aktor_{name}"])],
        "akcia_typy": [name for name in ACTIONS if bool(row[f"akcia_{name}"])],
        **{column: details(column) for column in DETAIL_COLUMNS},
        "atribut_integrity": bool(row["atribut_integrity"]),
        "atribut_availability": bool(row["atribut_availability"]),
    }


# ---------------------------------------------------------------- testovacie incidenty

@lru_cache(maxsize=1)
def test_incidents():
    """Testovacie incidenty z predikcia.ipynb spolu s ich riadkami z vcdb_clean.csv."""
    predictions = pd.read_csv(PREDICTIONS_PATH, usecols=["zaznam_id"])
    clean = context()["clean"]
    return clean[clean["zaznam_id"].isin(predictions["zaznam_id"])].reset_index(drop=True)


def random_test_incident(seed=None):
    """Náhodný testovací incident ako vstup formulára a jeho skutočný dopad."""
    tests = test_incidents()
    row = tests.iloc[int(np.random.default_rng(seed).integers(len(tests)))]
    return {
        "vstup": from_clean_row(row),
        "zaznam_id": int(row["zaznam_id"]),
        "skutocny_dopad": row["dopad"],
        "pocet_zaznamov": int(row["pocet_zaznamov"]),
        "rok": None if pd.isna(row["rok"]) else int(row["rok"]),
        "popis": row["popis"] if pd.notna(row["popis"]) else "",
    }


# ---------------------------------------------------------------- preskripcia

def default_frequency(sector, pattern):
    """Podiel vzoru v odvetví medzi reprezentatívnymi incidentmi krát počet incidentov za rok."""
    ctx = context()
    share = ctx["share"].loc[sector] if sector in ctx["share"].index else ctx["share_all"]
    return INCIDENTS_PER_YEAR * float(share.get(pattern, 0.0))


def option_controls(pattern):
    """CIS opatrenia, ktoré patria k jednotlivým typom opatrení pre daný vzor útoku."""
    controls = context()["controls"]
    rows = controls[controls["vzor_utoku"] == pattern]
    prevention = rows[rows["typ_opatrenia"] == "prevencia"]
    response = rows[rows["typ_opatrenia"] != "prevencia"]
    if 17 not in set(response["cis_cislo"]):
        response = pd.concat([response, pd.DataFrame([{"cis_cislo": 17, "typ_opatrenia": "reakcia"}])])
    return prevention, response


def option_costs(pattern):
    prevention, response = option_controls(pattern)
    prevention_cost = prevention["typ_opatrenia"].map(CONTROL_COST).sum()
    response_cost = response["typ_opatrenia"].map(CONTROL_COST).sum()
    return np.array([MONITORING_COST, prevention_cost, response_cost, prevention_cost + response_cost], dtype=float)


def control_list(pattern, option):
    prevention, response = option_controls(pattern)
    chosen = {"Akceptovať a monitorovať": [], "Prevencia": [prevention], "Detekcia a reakcia": [response],
              "Komplexná ochrana": [prevention, response]}[option]
    numbers = sorted({int(number) for frame in chosen for number in frame["cis_cislo"]})
    return ", ".join(f"CIS {number}" for number in numbers) or "monitorovanie"


def residual_share(horizon=HORIZON_YEARS):
    """Časť straty, ktorá po zavedení opatrenia zostane, s ohľadom na čas zavedenia v horizonte."""
    effective = (12 * horizon - OPTIONS["mesiace zavedenia"].to_numpy()) / (12 * horizon)
    return (1 - OPTIONS["menej incidentov"].to_numpy() * effective) * (1 - OPTIONS["menšia strata"].to_numpy() * effective)


def expected_loss(distribution, frequency, loss=None):
    losses = LOSS.to_numpy() if loss is None else np.asarray(loss, dtype=float)
    return INCIDENTS_PER_YEAR * frequency * float(np.asarray(distribution) @ losses)


def total_costs(distribution, frequency, costs, loss=None, horizon=HORIZON_YEARS):
    """Ročné celkové náklady každého opatrenia: cena plus strata, ktorá zostane."""
    return costs + expected_loss(distribution, frequency, loss) * residual_share(horizon)


def predict(incident):
    """Kalibrované pravdepodobnosti tried dopadu pre jeden incident."""
    return calibrated_probabilities(context()["bundle"], to_frame(incident))[0]


def assess(incident, frequency=None, *, loss=None, cost_factor=1.0, horizon=HORIZON_YEARS):
    """Vyhodnotí jeden incident: dopad, riziko, opatrenie a porovnanie opatrení."""
    row = to_row(incident)
    pattern = row["vzor_utoku"]
    default = default_frequency(row["odvetvie"], pattern)
    frequency = default if frequency is None else float(frequency)
    probabilities = predict(incident)

    losses = LOSS.to_numpy() if loss is None else np.asarray(loss, dtype=float)
    costs = option_costs(pattern) * cost_factor
    totals = total_costs(probabilities, frequency, costs, losses, horizon)
    choice = int(totals.argmin())
    option = OPTION_NAMES[choice]
    comparison = [
        {
            "opatrenie": name,
            "opatrenia_cis": control_list(pattern, name),
            "cena": float(costs[index]),
            "zostavajuca_strata": float(totals[index] - costs[index]),
            "celkove_naklady": float(totals[index]),
            "odporucane": index == choice,
        }
        for index, name in enumerate(OPTION_NAMES)
    ]
    return {
        "vzor_utoku": pattern,
        "odvetvie": row["odvetvie"],
        "frekvencia": frequency,
        "frekvencia_predvolena": default,
        "pravdepodobnosti": dict(zip(LABELS, map(float, probabilities))),
        "predikovany_dopad": LABELS[int(probabilities.argmax())],
        "strata_incidentu": float(probabilities @ losses),
        "ocakavana_strata": expected_loss(probabilities, frequency, losses),
        "opatrenie": option,
        "opatrenia_cis": control_list(pattern, option),
        "cena_opatrenia": float(costs[choice]),
        "zostavajuca_strata": float(totals[choice] - costs[choice]),
        "cisty_prinos": float(totals[0] - totals[choice]),
        "porovnanie": comparison,
    }


def thresholds():
    """Od akej očakávanej ročnej straty sa oplatí každé opatrenie, rovnako ako v notebooku."""
    risk_grid = np.linspace(0, 1_500_000, 30_001)
    residual = residual_share()
    rows = []
    for pattern in PATTERNS:
        best = (option_costs(pattern)[None, :] + risk_grid[:, None] * residual[None, :]).argmin(axis=1)
        rows.append({
            "vzor útoku": pattern,
            **{f"{OPTION_NAMES[option]} od (€)": round(risk_grid[np.argmax(best == option)], -2) if (best == option).any() else np.nan
               for option in range(1, len(OPTION_NAMES))},
        })
    return pd.DataFrame(rows)


def cost_table():
    rows = []
    for pattern in PATTERNS:
        costs = option_costs(pattern)
        rows.append({
            "vzor útoku": pattern,
            **{f"{name} (€)": costs[index] for index, name in enumerate(OPTION_NAMES)},
            "prevencia": control_list(pattern, "Prevencia"),
            "detekcia a reakcia": control_list(pattern, "Detekcia a reakcia"),
        })
    return pd.DataFrame(rows)


def load_register():
    """Register scenárov zoradený podľa priority. Scenáre bez opatrenia sú na konci."""
    register = pd.read_csv(REGISTER_PATH)
    return register.sort_values(["priorita", "očakávaná strata (€)"], ascending=[True, False], na_position="last",
                                ignore_index=True)


# ---------------------------------------------------------------- scenáre, stratégie a rozpočet
# Rovnaký výpočet ako časti 1, 4 a 5 notebooku preskriptivna_udrzba.ipynb (grafy 8 a 9)

MIN_SCENARIO_INCIDENTS = 10
STRATEGY_OURS = "Podľa predikovaného dopadu"
STRATEGY_LABELS = {
    "S dokonalou znalosťou": "S dokonalou znalosťou dopadu (teoretické optimum)",
    STRATEGY_OURS: "Podľa predikovaného dopadu (naše riešenie)",
    "Bez modelu, podľa histórie": "Bez modelu, podľa histórie",
    "Podľa najpravdepodobnejšej triedy": "Podľa najpravdepodobnejšej triedy",
    "Akceptovať a monitorovať": "Všade akceptovať",
    "Prevencia": "Všade prevencia",
    "Detekcia a reakcia": "Všade detekcia a reakcia",
    "Komplexná ochrana": "Všade komplexná ochrana",
}
BUDGET_ORDERS = ["Podľa prínosu na euro", "Podľa frekvencie"]


def _scenario_masks(frame, sectors, patterns):
    """Pre každý scenár maska incidentov, z ktorých sa odhaduje dopad, a úroveň odhadu."""
    result = []
    for sector in sectors:
        for pattern in patterns:
            for mask, level in [
                ((frame["odvetvie"] == sector) & (frame["vzor_utoku"] == pattern), "odvetvie a vzor"),
                (frame["vzor_utoku"] == pattern, "iba vzor"),
                (pd.Series(True, index=frame.index), "všetky incidenty"),
            ]:
                if mask.sum() >= MIN_SCENARIO_INCIDENTS:
                    result.append((mask.to_numpy(), level))
                    break
    return result


def _distributions(masks, probabilities):
    return np.array([probabilities[mask].mean(axis=0) for mask, _ in masks])


def _cost_matrix(distribution, frequency, costs):
    """Ako total_costs, ale pre všetky scenáre naraz: matica scenáre × opatrenia."""
    base = INCIDENTS_PER_YEAR * frequency * (distribution @ LOSS.to_numpy())
    return costs + base[:, None] * residual_share()[None, :]


def _one_hot(impacts):
    return np.eye(len(LABELS))[pd.Categorical(impacts, categories=LABELS).codes]


@lru_cache(maxsize=1)
def scenario_analysis():
    """Scenáre odvetvie × vzor útoku, porovnanie stratégií a krivky rozpočtu z vcdb_predikcie.csv."""
    ctx = context()
    clean = ctx["clean"]
    predictions = pd.read_csv(PREDICTIONS_PATH)
    patterns = list(dict.fromkeys(ctx["controls"]["vzor_utoku"]))
    representative = clean[clean["reprezentativny"]]
    sectors = list(representative.loc[representative["odvetvie"] != "Neznáme", "odvetvie"].value_counts().head(6).index)
    test_ids = set(predictions["zaznam_id"])
    history = clean[clean["dopad"].notna() & ~clean["zaznam_id"].isin(test_ids)].reset_index(drop=True)

    scenarios = pd.DataFrame([(sector, pattern) for sector in sectors for pattern in patterns],
                             columns=["odvetvie", "vzor_utoku"])
    frequency = np.array([ctx["share"].loc[sector].get(pattern, 0.0)
                          for sector, pattern in zip(scenarios["odvetvie"], scenarios["vzor_utoku"])])
    test_masks = _scenario_masks(predictions, sectors, patterns)
    dist_model = _distributions(test_masks, predictions[[f"p_lgbm_{label}" for label in LABELS]].to_numpy())
    dist_actual = _distributions(test_masks, _one_hot(predictions["dopad"]))
    dist_history = _distributions(_scenario_masks(history, sectors, patterns), _one_hot(history["dopad"]))
    costs = np.array([option_costs(pattern) for pattern in scenarios["vzor_utoku"]])
    rows = np.arange(len(scenarios))

    model_costs = _cost_matrix(dist_model, frequency, costs)
    actual_costs = _cost_matrix(dist_actual, frequency, costs)
    decisions = {name: np.full(len(scenarios), index) for index, name in enumerate(OPTION_NAMES)}
    decisions[STRATEGY_OURS] = model_costs.argmin(axis=1)
    decisions["Podľa najpravdepodobnejšej triedy"] = np.array([0, 2, 3])[dist_model.argmax(axis=1)]
    decisions["Bez modelu, podľa histórie"] = _cost_matrix(dist_history, frequency, costs).argmin(axis=1)
    decisions["S dokonalou znalosťou"] = actual_costs.argmin(axis=1)
    strategies = pd.DataFrame([
        {"stratégia": STRATEGY_LABELS[name], "naša": name == STRATEGY_OURS,
         "ročné náklady spolu (€)": float(actual_costs[rows, chosen].sum())}
        for name, chosen in decisions.items()
    ])
    strategies["na organizáciu (€)"] = strategies["ročné náklady spolu (€)"] / len(sectors)
    strategies = strategies.sort_values("na organizáciu (€)", ignore_index=True)

    decision = decisions[STRATEGY_OURS]
    chosen_cost = costs[rows, decision]
    benefit = model_costs[:, 0] - model_costs[rows, decision] + chosen_cost - MONITORING_COST
    worthwhile = decision != 0
    actual_reduction = actual_costs[:, 0] - actual_costs[rows, decision] + chosen_cost - MONITORING_COST
    scenarios["frekvencia za rok"] = frequency
    scenarios["opatrenie"] = np.array(OPTION_NAMES)[decision]
    scenarios["opatrenia CIS"] = [control_list(pattern, option)
                                  for pattern, option in zip(scenarios["vzor_utoku"], scenarios["opatrenie"])]
    scenarios["cena (€)"] = chosen_cost - MONITORING_COST
    scenarios["znížená strata (€)"] = actual_reduction

    orders = {
        BUDGET_ORDERS[0]: np.argsort(-(benefit / np.maximum(chosen_cost - MONITORING_COST, 1))),
        BUDGET_ORDERS[1]: np.argsort(-frequency),
    }
    curves = {}
    for name, order in orders.items():
        steps = scenarios.iloc[[index for index in order if worthwhile[index]]].reset_index(drop=True)
        steps.insert(0, "poradie", np.arange(1, len(steps) + 1))
        steps["rozpočet (€)"] = steps["cena (€)"].cumsum()
        steps["znížená strata spolu (€)"] = steps["znížená strata (€)"].cumsum()
        curves[name] = steps
    return {"sectors": sectors, "strategies": strategies, "curves": curves}


def strategy_comparison():
    """Ročné náklady stratégií pri skutočnom dopade, spolu a na jednu organizáciu, od najlacnejšej."""
    return scenario_analysis()["strategies"].copy()


def budget_curves():
    """Pre každé poradie scenáre v poradí zavádzania s kumulatívnym rozpočtom a zníženou stratou."""
    return {name: steps.copy() for name, steps in scenario_analysis()["curves"].items()}


def budget_total():
    """Ročná cena všetkých odporúčaných opatrení bez monitorovania."""
    return float(scenario_analysis()["curves"][BUDGET_ORDERS[0]]["cena (€)"].sum())


def budget_coverage(budget, order=BUDGET_ORDERS[0]):
    """Scenáre, ktoré sa pokryjú z ročného rozpočtu, a znížená strata. Ako v notebooku sa ide presne v poradí."""
    steps = scenario_analysis()["curves"][order]
    covered = steps[steps["rozpočet (€)"] <= budget + 1e-9].copy()
    reduced = float(covered["znížená strata spolu (€)"].iloc[-1]) if len(covered) else 0.0
    return covered, reduced


def assessment_timeline(records):
    """Uložené hodnotenia zoradené podľa času s kumulatívnym počtom podľa dopadu a kumulatívnou stratou."""
    frame = records.copy()
    frame["čas"] = pd.to_datetime(frame["vytvorene"], errors="coerce")
    frame = frame.dropna(subset=["čas"]).sort_values(["čas", "id"], ignore_index=True)
    for label in LABELS:
        frame[f"počet {label}"] = (frame["predikovany_dopad"] == label).cumsum()
    frame["počet spolu"] = np.arange(1, len(frame) + 1)
    frame["strata spolu (€)"] = frame["ocakavana_strata"].cumsum()
    return frame


# ---------------------------------------------------------------- databáza

SCHEMA = """
CREATE TABLE IF NOT EXISTS hodnotenia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vytvorene TEXT NOT NULL,
    zdroj TEXT NOT NULL,
    nazov TEXT NOT NULL DEFAULT '',
    odvetvie TEXT NOT NULL,
    vzor_utoku TEXT NOT NULL,
    frekvencia REAL NOT NULL,
    p_nizky REAL NOT NULL,
    p_stredny REAL NOT NULL,
    p_vysoky REAL NOT NULL,
    predikovany_dopad TEXT NOT NULL,
    skutocny_dopad TEXT,
    strata_incidentu REAL NOT NULL,
    ocakavana_strata REAL NOT NULL,
    opatrenie TEXT NOT NULL,
    opatrenia_cis TEXT NOT NULL,
    cena_opatrenia REAL NOT NULL,
    zostavajuca_strata REAL NOT NULL,
    cisty_prinos REAL NOT NULL,
    vstup TEXT NOT NULL
)
"""
RECORD_COLUMNS = [
    "id", "vytvorene", "zdroj", "nazov", "odvetvie", "vzor_utoku", "frekvencia",
    "p_nizky", "p_stredny", "p_vysoky", "predikovany_dopad", "skutocny_dopad",
    "strata_incidentu", "ocakavana_strata", "opatrenie", "opatrenia_cis",
    "cena_opatrenia", "zostavajuca_strata", "cisty_prinos", "vstup",
]


def uses_azure_sql(path=None):
    return path is None and bool(os.environ.get("AZURE_SQL_CONNECTION_STRING"))


@lru_cache(maxsize=1)
def azure_sql_driver():
    import mssql_python

    mssql_python.pooling(max_size=8, idle_timeout=30)
    return mssql_python


def connect(path=None):
    if uses_azure_sql(path):
        driver = azure_sql_driver()
        deadline = time.monotonic() + 120
        delays = (5, 10, 20, 30, 30)
        for attempt in range(len(delays) + 1):
            try:
                return driver.connect(
                    os.environ["AZURE_SQL_CONNECTION_STRING"],
                    timeout=max(1, min(60, int(deadline - time.monotonic()))),
                )
            except driver.OperationalError as error:
                # Serverless SQL rejects connections while resuming (40613).
                # Retry opening only: replaying a write could duplicate records.
                message = str(error).lower()
                transient = any(code in message for code in ("40613", "40197", "40501")) or (
                    "database" in message and "not currently available" in message
                )
                remaining = deadline - time.monotonic()
                if not transient or attempt == len(delays) or remaining <= 0:
                    raise
                time.sleep(min(delays[attempt], remaining))
                if time.monotonic() >= deadline:
                    raise
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(SCHEMA)
    return connection


def save_assessment(incident, result, source, name="", actual_impact=None, path=None, connection=None):
    """Uloží hodnotenie do tabuľky hodnotenia a vráti jeho id."""
    probabilities = result["pravdepodobnosti"]
    values = {
        "vytvorene": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "zdroj": source,
        "nazov": (name or "").strip(),
        "odvetvie": result["odvetvie"],
        "vzor_utoku": result["vzor_utoku"],
        "frekvencia": result["frekvencia"],
        "p_nizky": probabilities["nízky"],
        "p_stredny": probabilities["stredný"],
        "p_vysoky": probabilities["vysoký"],
        "predikovany_dopad": result["predikovany_dopad"],
        "skutocny_dopad": actual_impact,
        "strata_incidentu": result["strata_incidentu"],
        "ocakavana_strata": result["ocakavana_strata"],
        "opatrenie": result["opatrenie"],
        "opatrenia_cis": result["opatrenia_cis"],
        "cena_opatrenia": result["cena_opatrenia"],
        "zostavajuca_strata": result["zostavajuca_strata"],
        "cisty_prinos": result["cisty_prinos"],
        "vstup": json.dumps(incident, ensure_ascii=False, sort_keys=True),
    }
    def insert(db):
        output = " OUTPUT INSERTED.id" if uses_azure_sql(path) else ""
        cursor = db.execute(
            f"INSERT INTO hodnotenia ({', '.join(values)}){output} VALUES ({', '.join('?' * len(values))})",
            list(values.values()),
        )
        return int(cursor.fetchone()[0]) if uses_azure_sql(path) else cursor.lastrowid
    if connection is not None:
        return insert(connection)
    with closing(connect(path)) as db, db:
        return insert(db)


def load_assessments(path=None):
    """Všetky uložené hodnotenia zoradené od najvyššej očakávanej straty."""
    with closing(connect(path)) as connection:
        if uses_azure_sql(path):
            cursor = connection.execute(
                f"SELECT {', '.join(RECORD_COLUMNS)} FROM hodnotenia ORDER BY ocakavana_strata DESC, id DESC"
            )
            return pd.DataFrame.from_records([tuple(row) for row in cursor.fetchall()], columns=RECORD_COLUMNS)
        return pd.read_sql_query(
            f"SELECT {', '.join(RECORD_COLUMNS)} FROM hodnotenia ORDER BY ocakavana_strata DESC, id DESC",
            connection,
        )


def delete_assessments(ids, path=None):
    ids = [int(value) for value in ids]
    if not ids:
        return 0
    with closing(connect(path)) as connection, connection:
        cursor = connection.execute(f"DELETE FROM hodnotenia WHERE id IN ({', '.join('?' * len(ids))})", ids)
        return cursor.rowcount


# ---------------------------------------------------------------- overenie

def verify():
    """Porovná pravdepodobnosti zo vstupu formulára s predikciou nad pôvodným riadkom vcdb_clean.csv."""
    tests = test_incidents()
    bundle = context()["bundle"]
    direct = calibrated_probabilities(bundle, tests)
    via_form = calibrated_probabilities(
        bundle, pd.concat([to_frame(from_clean_row(row)) for _, row in tests.iterrows()], ignore_index=True)
    )
    difference = np.abs(direct - via_form).max(axis=1)
    patterns = [to_row(from_clean_row(row))["vzor_utoku"] for _, row in tests.iterrows()]
    return {
        "incidenty": len(tests),
        "max_rozdiel": float(difference.max()),
        "priemerny_rozdiel": float(difference.mean()),
        "rozdiel_pod_0_01": float((difference < 0.01).mean()),
        "rovnaka_trieda": float((direct.argmax(axis=1) == via_form.argmax(axis=1)).mean()),
        "rovnaky_vzor": float((np.array(patterns) == tests["vzor_utoku"].to_numpy()).mean()),
    }


if __name__ == "__main__":
    result = verify()
    print(f"Testovacie incidenty: {result['incidenty']}")
    print(f"Najväčší rozdiel pravdepodobnosti: {result['max_rozdiel']:.4f}, priemerný: {result['priemerny_rozdiel']:.5f}")
    print(f"Rozdiel pod 0,01: {result['rozdiel_pod_0_01']:.1%}, rovnaká trieda: {result['rovnaka_trieda']:.1%}, "
          f"rovnaký vzor útoku: {result['rovnaky_vzor']:.1%}")
