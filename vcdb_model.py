"""Príprava znakov pre predikciu dopadu incidentu z dát VCDB.

Funkcie sú v samostatnom module, aby sa uložený model dal načítať aj mimo notebooku.
"""

import numpy as np
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

LABELS = ["nízky", "stredný", "vysoký"]

MULTI = ["akcia_variety", "akcia_vektory", "aktor_variety", "aktivum_variety", "typy_dat", "motiv", "sposob_odhalenia"]
CATEGORICAL = ["odvetvie", "velkost_organizacie", "krajina_skupina", "cielenost", "vzor_utoku"]
FLAGS = (
    [f"aktor_{name}" for name in ["external", "internal", "partner", "unknown"]]
    + [f"akcia_{name}" for name in ["hacking", "malware", "social", "error", "misuse", "physical", "environmental", "unknown"]]
    + [f"aktivum_{name}" for name in ["server", "zariadenie_pouzivatela", "nosic_dat", "osoba", "terminal", "sietove_zariadenie"]]
    + ["atribut_integrity", "atribut_availability", "ransomware"]
)


def prepare(frame):
    """Doplní prázdne hodnoty a zjednoduší krajinu."""
    frame = frame.copy()
    for column in MULTI:
        frame[column] = frame[column].fillna("")
    country = frame["krajina"].fillna("Unknown")
    frame["krajina_skupina"] = np.where(country.isin(["US", "GB", "CA", "Unknown"]), country, "iná")
    frame[FLAGS] = frame[FLAGS].astype(float)
    return frame


def to_float32(matrix):
    return sparse.csr_matrix(matrix, dtype=np.float32)


def make_features():
    return Pipeline([
        ("prepare", FunctionTransformer(prepare)),
        ("columns", ColumnTransformer(
            [(column, CountVectorizer(token_pattern=r"[^;]+", lowercase=False, binary=True, min_df=5), column)
             for column in MULTI]
            + [("categorical", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20), CATEGORICAL),
               ("flags", "passthrough", FLAGS)],
            sparse_threshold=1.0,
        )),
        ("float32", FunctionTransformer(to_float32, accept_sparse=True)),
    ])


def calibrated_probabilities(bundle, frame):
    """Kalibrované pravdepodobnosti tried dopadu z modelu uloženého v predikcia_vcdb.ipynb."""
    raw = bundle["pipeline"].predict_proba(frame)
    return bundle["calibrator"].predict_proba(np.log(np.clip(raw, 1e-6, 1)))
