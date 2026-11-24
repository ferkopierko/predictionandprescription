"""REST API nad rovnakým modelom a databázou ako aplikácia app.py.

Spustenie: uvicorn api:app --port 8000
Dokumentácia API: http://localhost:8000/docs
"""

import math
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import opatrenia as op

app = FastAPI(
    title="Hodnotenie rizika bezpečnostných incidentov",
    description="Predikcia dopadu incidentu nad VCDB a výber opatrenia CIS Controls podľa rizika, nákladov a času.",
    version="1.0",
)


class Incident(BaseModel):
    """Incident tak, ako ho analytik pozná hneď po odhalení. Povolené hodnoty vracia GET /api/moznosti."""

    odvetvie: str = "Neznáme"
    velkost_organizacie: str = "neznáma"
    krajina: str = "Unknown"
    cielenost: str = "neznáma"
    aktor_typy: list[str] = Field(default_factory=list, examples=[["external"]])
    akcia_typy: list[str] = Field(default_factory=list, examples=[["hacking"]])
    aktor_variety: list[str] = Field(default_factory=list, examples=[["external:Organized crime"]])
    akcia_variety: list[str] = Field(default_factory=list, examples=[["hacking:SQLi"]])
    akcia_vektory: list[str] = Field(default_factory=list, examples=[["hacking:Web application"]])
    aktivum_variety: list[str] = Field(default_factory=list, examples=[["S - Database"]])
    typy_dat: list[str] = Field(default_factory=list, examples=[["Personal"]])
    motiv: list[str] = Field(default_factory=list, examples=[["Financial"]])
    sposob_odhalenia: list[str] = Field(default_factory=list)
    atribut_integrity: bool = False
    atribut_availability: bool = False


class Request(Incident):
    nazov: str = Field("", max_length=200, description="Nepovinný názov hodnotenia")
    frekvencia: float | None = Field(
        None, ge=0, le=100,
        description="Očakávaný počet incidentov tohto vzoru za rok. Ak chýba, použije sa podiel vzoru v odvetví.",
    )
    zdroj: Literal["API", "simulácia"] = Field(
        "API", description="Pôvod hodnotenia. Generátor simulacia.py posiela hodnotu simulácia.",
    )
    skutocny_dopad: Literal["nízky", "stredný", "vysoký"] | None = Field(
        None, description="Skutočný dopad, ak je známy (napríklad pri testovacom incidente z VCDB). Model ho nepoužíva.",
    )


def _ensure_data():
    missing = op.missing_files()
    if missing:
        raise HTTPException(503, f"Chýbajú súbory {', '.join(path.name for path in missing)}. Spustite notebooky podľa README.md.")


def _records(frame):
    """Riadky tabuľky ako JSON. Chýbajúce hodnoty sú null."""
    return [
        {key: None if isinstance(value, float) and math.isnan(value) else value for key, value in row.items()}
        for row in frame.astype(object).to_dict(orient="records")
    ]


@app.get("/api/moznosti", summary="Povolené hodnoty polí incidentu")
def moznosti():
    _ensure_data()
    return op.choices()


@app.post("/api/hodnotenie", status_code=201, summary="Vyhodnotí incident a uloží výsledok do databázy")
def hodnotenie(request: Request):
    _ensure_data()
    incident = request.model_dump(exclude={"nazov", "frekvencia", "zdroj", "skutocny_dopad"})
    errors = op.validate(incident)
    if errors:
        raise HTTPException(422, errors)
    result = op.assess(incident, request.frekvencia)
    record_id = op.save_assessment(
        incident, result, source=request.zdroj, name=request.nazov, actual_impact=request.skutocny_dopad,
    )
    return {"id": record_id, **result}


@app.get("/api/hodnotenia", summary="Uložené hodnotenia zoradené podľa očakávanej straty")
def hodnotenia():
    records = op.load_assessments().drop(columns="vstup")
    return _records(records)


@app.get("/api/register", summary="Register 48 scenárov rizika z preskriptivna_udrzba.ipynb")
def register():
    _ensure_data()
    return _records(op.load_register())
