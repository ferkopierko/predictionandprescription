"""REST API nad rovnakým modelom a databázou ako aplikácia app.py.

Spustenie: uvicorn api:app --port 8000
Dokumentácia API: http://localhost:8000/docs
"""

import math
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from hrontech import opatrenia as op
from hrontech import firma as co

app = FastAPI(
    title="safetyfirst · HronTech Strojárne",
    description="Predikcia dopadu incidentu nad VCDB a výber opatrenia CIS Controls podľa rizika, nákladov a času.",
    version="1.0",
)


class Incident(BaseModel):
    """Incident tak, ako ho analytik pozná hneď po odhalení. Povolené hodnoty vracia GET /api/moznosti."""

    model_config = ConfigDict(extra="forbid")
    odvetvie: str = "Výroba"
    velkost_organizacie: str = "malá"
    krajina: str = "iná"
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
    asset_id: str = Field(description="ID aktíva z GET /api/firma/aktiva")
    finding_id: str | None = None
    case_id: int | None = Field(None, ge=1)
    zdroj: Literal["API", "simulácia"] = "API"
    skutocny_dopad: Literal["nízky", "stredný", "vysoký"] | None = Field(
        None, description="Voliteľný skutočne zistený dopad. Firemný generátor ho nevymýšľa ani neposiela.",
    )
    nazov: str = Field("", max_length=200, description="Nepovinný názov hodnotenia")
    frekvencia: float | None = Field(
        None, ge=0, le=100,
        description="Očakávaný počet incidentov tohto vzoru za rok. Ak chýba, použije sa podiel vzoru v odvetví.",
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
    incident = request.model_dump(exclude={"nazov", "frekvencia", "asset_id", "finding_id", "case_id", "zdroj", "skutocny_dopad"})
    try:
        defaults = co.incident_input(request.asset_id)
        if not incident["aktivum_variety"]:
            incident["aktivum_variety"] = defaults["aktivum_variety"]
        if not incident["typy_dat"]:
            incident["typy_dat"] = defaults["typy_dat"]
        record_id, result = co.assess_and_save(incident, request.asset_id, request.frekvencia, request.nazov,
                                             request.finding_id, request.case_id, source=request.zdroj, actual_impact=request.skutocny_dopad)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"id": record_id, **result}


@app.get("/api/hodnotenia", summary="Uložené hodnotenia zoradené podľa očakávanej straty")
def hodnotenia():
    records = co.assessments().drop(columns="vstup")
    return _records(records)


@app.get("/api/register", summary="Plánovacie scenáre firmy HronTech")
def register():
    _ensure_data()
    return _records(co.risk_register())


@app.get("/api/firma", summary="Profil simulovanej firmy")
def firma():
    return co.profile()


@app.get("/api/firma/aktiva", summary="Inventár aktív a webov")
def aktiva():
    return _records(co.assets())


@app.get("/api/firma/zranitelnosti", summary="Modelové bezpečnostné zistenia")
def zranitelnosti():
    return _records(co.findings())


@app.get("/api/firma/incidenty", summary="Evidované simulované incidenty")
def incidenty():
    return _records(co.cases())


@app.get("/api/firma/scenare", summary="Pripravené scenáre simulácie")
def scenare():
    return co.SCENARIOS


class SimulationRequest(BaseModel):
    scenario: str
    finding_id: str | None = None


@app.post("/api/firma/simulacia", status_code=201, summary="Vytvorí modelový incident bez útoku na sieť")
def simulacia(request: SimulationRequest):
    try:
        return co.start_simulation(request.scenario, request.finding_id)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


class FindingStatusRequest(BaseModel):
    status: str
    note: str = Field("", max_length=2000)


@app.patch("/api/firma/zranitelnosti/{finding_id}", summary="Uloží stav riešenia zraniteľnosti")
def stav_zranitelnosti(finding_id: str, request: FindingStatusRequest):
    try:
        co.set_finding_status(finding_id, request.status, request.note)
        return co.finding(finding_id)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
