"""Predikcia závažnosti zraniteľnosti a výber opatrenia pre aplikáciu app.py.

Model, kalibrácia a predpoklady zodpovedajú notebooku preskriptivna_udrzba.ipynb.
Spustenie `python opatrenia.py` model naučí a uloží.
"""

import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "processed" / "cve_clean.csv"
MODEL_PATH = ROOT / "data" / "processed" / "model_opatrenia.joblib"
RECORDS_PATH = ROOT / "data" / "processed" / "pridane_zaznamy.csv"
TEST_RESULTS_PATH = ROOT / "data" / "processed" / "odporucania_opatreni.csv"
FIGURES_DIR = ROOT / "figures"

LABELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SEED = 42

LEAKAGE_PATTERN = (
    r"\bcvss(?:v?\d|:|\b)"
    r"|base score"
    r"|severity"
    r"|\brated\s+(?:as\s+)?(?:critical|high|moderate|medium|low)\b"
)

HOURLY_RATE = 60
PROTECTION_RESIDUAL = 0.3

SEVERITY_ASSUMPTIONS = pd.DataFrame({
    "škoda pri zneužití (€)": [1_000, 10_000, 50_000, 200_000],
    "pravdepodobnosť zneužitia za 90 dní": [0.005, 0.01, 0.03, 0.08],
}, index=LABELS)

ACTION_NAMES = ["Monitorovanie", "Plánovaná oprava", "Dočasná ochrana", "Núdzová oprava"]
ACTION_ASSUMPTIONS = pd.DataFrame({
    "hodiny práce": [1, 4, 10, 16],
    "dni do ochrany": [90, 30, 2, 3],
    "dni do opravy": [90, 30, 14, 3],
}, index=ACTION_NAMES)

ACTION_STEPS = {
    "Monitorovanie": "Sledovať výskyt a správy o zneužití. Opraviť pri bežnej údržbe.",
    "Plánovaná oprava": "Zaradiť do mesačného cyklu záplat s bežným testovaním.",
    "Dočasná ochrana": "Nasadiť dočasnú ochranu, potom vykonať prioritnú opravu.",
    "Núdzová oprava": "Vykonať mimoriadnu zmenu mimo cyklu so zrýchleným testovaním a nasadením.",
}

COST = ACTION_ASSUMPTIONS["hodiny práce"].to_numpy(dtype=float) * HOURLY_RATE
_protect = ACTION_ASSUMPTIONS["dni do ochrany"].to_numpy(dtype=float)
_fix = ACTION_ASSUMPTIONS["dni do opravy"].to_numpy(dtype=float)
EXPOSURE = _protect + (_fix - _protect) * PROTECTION_RESIDUAL
DAILY_RISK = (
    SEVERITY_ASSUMPTIONS["škoda pri zneužití (€)"].to_numpy(dtype=float)
    * SEVERITY_ASSUMPTIONS["pravdepodobnosť zneužitia za 90 dní"].to_numpy(dtype=float)
    / 90
)

CWE_NAMES = {
    "CWE-20": "nesprávna validácia vstupu",
    "CWE-22": "path traversal",
    "CWE-78": "OS command injection",
    "CWE-79": "cross-site scripting",
    "CWE-89": "SQL injection",
    "CWE-94": "code injection",
    "CWE-119": "chyba v pamäti",
    "CWE-125": "čítanie mimo hraníc",
    "CWE-190": "pretečenie celého čísla",
    "CWE-200": "únik informácií",
    "CWE-269": "správa oprávnení",
    "CWE-284": "riadenie prístupu",
    "CWE-287": "nesprávne overenie",
    "CWE-306": "chýbajúce overenie",
    "CWE-352": "CSRF",
    "CWE-400": "vyčerpanie prostriedkov",
    "CWE-416": "use after free",
    "CWE-434": "nahrávanie nebezpečných súborov",
    "CWE-502": "deserializácia",
    "CWE-787": "zápis mimo hraníc",
    "CWE-798": "pevne zadané prihlasovacie údaje",
    "CWE-862": "chýbajúca autorizácia",
}

CONTROLS = {
    "CWE-79": "pravidlo WAF, prísna Content-Security-Policy",
    "CWE-89": "pravidlo WAF, obmedzenie práv databázového účtu",
    "CWE-20": "filtrovanie vstupov na proxy alebo WAF",
    "CWE-22": "pravidlo WAF, obmedzenie práv k súborom",
    "CWE-78": "izolácia služby, spustenie s minimálnymi právami",
    "CWE-77": "izolácia služby, spustenie s minimálnymi právami",
    "CWE-94": "izolácia služby, zákaz odchádzajúcich spojení",
    "CWE-119": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-120": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-125": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-787": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-416": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-190": "obmedzenie sieťového prístupu, izolácia procesu",
    "CWE-287": "prístup iba cez VPN, viacfaktorové overenie",
    "CWE-306": "prístup iba cez VPN, viacfaktorové overenie",
    "CWE-798": "zmena prihlasovacích údajov, prístup iba cez VPN",
    "CWE-269": "obmedzenie účtov, sledovanie zmien oprávnení",
    "CWE-284": "dočasné sprísnenie prístupových pravidiel",
    "CWE-862": "dočasné sprísnenie prístupových pravidiel",
    "CWE-863": "dočasné sprísnenie prístupových pravidiel",
    "CWE-200": "obmedzenie prístupu k službe, sledovanie prístupov",
    "CWE-352": "kontrola pôvodu požiadaviek na proxy, SameSite cookies",
    "CWE-434": "dočasný zákaz nahrávania súborov",
    "CWE-502": "obmedzenie sieťového prístupu k službe",
    "CWE-400": "obmedzenie počtu požiadaviek",
}

RECORD_COLUMNS = [
    "zaznam_id", "pridane", "cve_id", "description", "cwe_text",
    *[f"P_{label}" for label in LABELS],
    "ocakavane_denne_riziko", "opatrenie",
]


def _to_float32(matrix):
    return sparse.csr_matrix(matrix, dtype=np.float32)


def _make_features():
    return ColumnTransformer([
        ("text", TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=5,
            max_df=0.9,
            max_features=30_000,
            sublinear_tf=True,
        ), "description"),
        ("cwe", CountVectorizer(
            lowercase=False,
            token_pattern=r"CWE-\d+",
            binary=True,
        ), "cwe_text"),
    ])


def _load_modeling_data():
    scored = pd.read_csv(DATA_PATH).dropna(subset=["severity_v3"])
    has_leakage = scored["description"].str.contains(LEAKAGE_PATTERN, case=False, regex=True)
    data = scored[~has_leakage].reset_index(drop=True)
    data["cwe_text"] = data["cwe_ids"].fillna("")
    data["target"] = pd.Categorical(data["severity_v3"], categories=LABELS, ordered=True).codes
    return data


def _log_probabilities(model, X):
    return np.log(np.clip(model.predict_proba(X), 1e-6, 1))


def train_and_save(path=MODEL_PATH):
    """Naučí LightGBM na dátach do roku 2018 a kalibruje ho na roku 2019."""
    data = _load_modeling_data()
    train = data[data["year"] <= 2018]
    calibration = data[data["year"] == 2019]

    features = _make_features()
    X_train = _to_float32(features.fit_transform(train))
    X_calibration = _to_float32(features.transform(calibration))

    model = lgb.LGBMClassifier(
        objective="multiclass",
        class_weight="balanced",
        n_estimators=118,
        learning_rate=0.1,
        num_leaves=63,
        min_child_samples=20,
        colsample_bytree=0.3,
        subsample=0.8,
        subsample_freq=1,
        random_state=SEED,
        deterministic=True,
        force_row_wise=True,
        n_jobs=4,
        verbosity=-1,
    )
    model.fit(X_train, train["target"].to_numpy())

    calibrator = LogisticRegression(C=1e4, max_iter=5000)
    calibrator.fit(_log_probabilities(model, X_calibration), calibration["target"].to_numpy())

    bundle = {"features": features, "model": model, "calibrator": calibrator}
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return bundle


def load_or_train(path=MODEL_PATH):
    return joblib.load(path) if path.exists() else train_and_save(path)


def predict_probabilities(bundle, frame):
    """Vráti kalibrované pravdepodobnosti tried pre stĺpce description a cwe_text."""
    X = _to_float32(bundle["features"].transform(frame))
    return bundle["calibrator"].predict_proba(_log_probabilities(bundle["model"], X))


def choose_actions(probabilities):
    """Pre každý riadok vyberie opatrenie s najnižšími očakávanými nákladmi."""
    expected_risk = probabilities @ DAILY_RISK
    return (COST[None, :] + EXPOSURE[None, :] * expected_risk[:, None]).argmin(axis=1), expected_risk


def thresholds():
    """Hodnoty r, pri ktorých sa mení najlacnejšie opatrenie."""
    points, current = [], 0
    while current < len(COST) - 1:
        r, following = min(
            ((COST[j] - COST[current]) / (EXPOSURE[current] - EXPOSURE[j]), j)
            for j in range(current + 1, len(COST))
            if EXPOSURE[j] < EXPOSURE[current]
        )
        points.append({"z opatrenia": ACTION_NAMES[current], "na opatrenie": ACTION_NAMES[following], "prah r (€ za deň)": r})
        current = following
    return pd.DataFrame(points)


def known_cwe_ids(bundle):
    names = bundle["features"].named_transformers_["cwe"].get_feature_names_out()
    return sorted(names, key=lambda value: int(value.split("-")[1]))


def recognized_terms(bundle, description):
    """Počet slov alebo dvojíc slov z popisu, ktoré model pozná."""
    vectorizer = bundle["features"].named_transformers_["text"]
    return int(vectorizer.transform([description]).nnz)


def temporary_control(cwe_ids):
    for cwe in cwe_ids:
        if cwe in CONTROLS:
            return CONTROLS[cwe]
    return "posúdiť individuálne podľa dotknutej služby"


def assess(bundle, description, cwe_ids, today=None):
    """Vyhodnotí jeden záznam: pravdepodobnosti, riziko, opatrenie a termíny."""
    today = today or date.today()
    frame = pd.DataFrame({"description": [description], "cwe_text": [" ".join(cwe_ids)]})
    probabilities = predict_probabilities(bundle, frame)
    decisions, expected_risk = choose_actions(probabilities)
    index, risk = int(decisions[0]), float(expected_risk[0])
    action = ACTION_NAMES[index]

    costs = pd.DataFrame({
        "opatrenie": ACTION_NAMES,
        "práca (€)": COST,
        "efektívne dni expozície": EXPOSURE,
        "očakávaná škoda (€)": EXPOSURE * risk,
        "očakávané náklady spolu (€)": COST + EXPOSURE * risk,
    })

    warnings = []
    if re.search(LEAKAGE_PATTERN, description, flags=re.IGNORECASE):
        warnings.append(
            "Popis uvádza skóre alebo závažnosť. Takéto záznamy boli z učenia vylúčené, "
            "preto môže byť odhad menej spoľahlivý."
        )
    terms = recognized_terms(bundle, description)
    if terms < 5:
        warnings.append(
            f"Model v popise rozpoznal iba {terms} výrazov. Odhad je slabo podložený, "
            "popis by mal byť podrobnejší a v angličtine."
        )

    return {
        "probabilities": dict(zip(LABELS, probabilities[0].tolist())),
        "predicted_class": LABELS[int(probabilities[0].argmax())],
        "expected_risk": risk,
        "action": action,
        "steps": ACTION_STEPS[action],
        "protect_by": today + timedelta(days=int(ACTION_ASSUMPTIONS.loc[action, "dni do ochrany"])),
        "fix_by": today + timedelta(days=int(ACTION_ASSUMPTIONS.loc[action, "dni do opravy"])),
        "control": temporary_control(cwe_ids),
        "costs": costs,
        "warnings": warnings,
    }


def load_records(path=RECORDS_PATH):
    if not path.exists():
        return pd.DataFrame(columns=RECORD_COLUMNS)
    return pd.read_csv(path, keep_default_na=False, dtype={"cve_id": str, "cwe_text": str, "zaznam_id": str})


def _save_records(records, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    records.to_csv(partial, index=False, encoding="utf-8")
    partial.replace(path)


def add_record(cve_id, description, cwe_ids, result, path=RECORDS_PATH):
    row = {
        "zaznam_id": uuid.uuid4().hex[:12],
        "pridane": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cve_id": cve_id,
        "description": description,
        "cwe_text": " ".join(cwe_ids),
        **{f"P_{label}": result["probabilities"][label] for label in LABELS},
        "ocakavane_denne_riziko": result["expected_risk"],
        "opatrenie": result["action"],
    }
    records = load_records(path)
    new_row = pd.DataFrame([row], columns=RECORD_COLUMNS)
    _save_records(new_row if records.empty else pd.concat([records, new_row], ignore_index=True), path)
    return row["zaznam_id"]


def delete_records(record_ids, path=RECORDS_PATH):
    records = load_records(path)
    _save_records(records[~records["zaznam_id"].isin(record_ids)], path)


if __name__ == "__main__":
    train_and_save()
    print(f"Model uložený: {MODEL_PATH}")
