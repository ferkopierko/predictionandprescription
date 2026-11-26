"""Persistent, explicitly fictional manufacturing company and its incident simulation.

Inventory findings and frequencies are authored simulation inputs, not scan results.
The trained VCDB classifier still predicts disclosure impact, not exploit probability.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

import opatrenia as op

COMPANY_ID = "hrontech"
STATUSES = ["Otvorená", "V riešení", "Odstránená"]
SEVERITIES = ["Kritická", "Vysoká", "Stredná", "Nízka"]
PROFILE = {
    "id": COMPANY_ID, "name": "HronTech Strojárne, s. r. o.",
    "location": "Banská Bystrica, Slovensko", "employees": 82,
    "description": "Výroba presných kovových dielov a CNC obrábanie pre priemyselných odberateľov.",
    "sector": "Výroba", "size": "malá", "country": "SK",
    "budget": 45_000, "losses": [5_000, 50_000, 500_000], "cost_factor": 0.35, "horizon": 3,
}

# id, name, category, count, address, technology, owner, criticality, model asset, data
ASSETS = [
    ("WEB-01", "Verejný web", "Weby", 1, "www.hrontech.example", "Linux / firemný CMS", "Marketing", "Stredná", "S - Web application", ["Internal"]),
    ("WEB-02", "Zákaznícky portál", "Weby", 1, "portal.hrontech.example", "Webová aplikácia / zákazky a výkresy", "Obchod a IT", "Kritická", "S - Web application", ["Personal", "Internal", "Secrets"]),
    ("SRV-01", "ERP a plánovanie výroby", "Servery", 1, "erp01.hrontech.internal", "Windows Server / ERP", "Plánovanie výroby", "Kritická", "S - Other", ["Internal", "Personal"]),
    ("SRV-02", "Databáza zákaziek", "Servery", 1, "sql01.hrontech.internal", "SQL databáza / zákazníci a objednávky", "IT správca", "Kritická", "S - Database", ["Personal", "Internal"]),
    ("SRV-03", "Súborový server CAD", "Servery", 1, "files01.hrontech.internal", "Windows Server / SMB", "Technická príprava", "Vysoká", "S - File", ["Secrets", "Internal"]),
    ("SRV-04", "Doménové radiče", "Servery", 2, "ad01 / ad02.hrontech.internal", "Active Directory", "IT správca", "Kritická", "S - Directory", ["Credentials", "System"]),
    ("BKP-01", "Zálohovací NAS", "Zálohy", 1, "backup01.hrontech.internal", "NAS / denné zálohy ERP a súborov", "IT správca", "Kritická", "S - Backup", ["Personal", "Secrets", "Internal"]),
    ("NET-01", "VPN a hraničný firewall", "Sieť", 1, "vpn.hrontech.example", "Firewall / vzdialený prístup", "IT správca", "Kritická", "S - Remote access", ["Credentials", "System"]),
    ("NET-02", "Spravované prepínače", "Sieť", 4, "10.42.0.0/24", "VLAN kancelária / výroba / servery", "IT správca", "Vysoká", "N - Router or switch", ["System"]),
    ("PC-01", "Kancelárske počítače", "Počítače", 25, "OFFICE-01 až OFFICE-25", "Windows 11 / účtovníctvo a obchod", "Administratíva", "Stredná", "U - Desktop", ["Personal", "Internal"]),
    ("CAD-01", "CAD/CAM pracovné stanice", "Počítače", 8, "CAD-01 až CAD-08", "Windows / CAD a CAM", "Konštrukcia", "Vysoká", "U - Desktop", ["Secrets", "Internal"]),
    ("NB-01", "Služobné notebooky", "Počítače", 6, "NB-01 až NB-06", "Windows 11 / vzdialený prístup", "Obchod a vedenie", "Vysoká", "U - Laptop", ["Personal", "Internal"]),
    ("OT-01", "Výrobné HMI terminály", "Výroba", 6, "HMI-01 až HMI-06", "Priemyselné PC / vizualizácia výroby", "Vedúci výroby", "Vysoká", "U - Desktop", ["Internal"]),
    ("OT-02", "CNC riadenie a výrobná brána", "Výroba", 12, "CNC-01 až CNC-12", "CNC riadenie / prenos výrobných programov", "Údržba výroby", "Kritická", "S - ICS", ["Internal", "Secrets"]),
    ("MAIL-01", "Firemná pošta", "Cloud", 82, "hrontech.example", "Cloudové poštové účty", "Všetci zamestnanci", "Vysoká", "S - Mail", ["Personal", "Internal", "Credentials"]),
]

# id, asset, title, severity, concrete remediation, estimated one-off remediation cost, scenario
FINDINGS = [
    ("SIM-001", "WEB-02", "Chýbajúce overenie oprávnení pri exporte zákaziek", "Kritická", "Doplniť kontrolu oprávnení a testy exportu v portáli.", 4_500, "portal"),
    ("SIM-002", "WEB-01", "Neaktualizované doplnky firemného CMS", "Vysoká", "Aktualizovať doplnky na testovacej kópii a nasadiť aktualizácie.", 1_200, "web"),
    ("SIM-003", "NET-01", "VPN účty nemajú viacfaktorové overenie", "Kritická", "Zaviesť MFA pre všetky VPN účty a zrušiť neaktívne prístupy.", 2_400, "vpn"),
    ("SIM-004", "CAD-01", "Používatelia CAD majú lokálne administrátorské práva", "Vysoká", "Odobrať bežným účtom lokálne administrátorské práva.", 1_600, "ransomware"),
    ("SIM-005", "PC-01", "Časť staníc nemá aktuálnu ochranu koncových bodov", "Vysoká", "Nasadiť a skontrolovať centrálnu ochranu všetkých staníc.", 3_500, "ransomware"),
    ("SIM-006", "MAIL-01", "Poštové účty nemajú jednotne zapnuté MFA", "Vysoká", "Zapnúť MFA a zakázať staré prihlasovacie protokoly.", 2_000, "phishing"),
    ("SIM-007", "SRV-03", "Zdieľaný priečinok výkresov je prístupný všetkým", "Vysoká", "Obmedziť prístupy ku CAD dátam podľa pracovnej roly.", 1_400, "export"),
    ("SIM-008", "BKP-01", "Chýba oddelená nemenná kópia záloh", "Kritická", "Zriadiť oddelenú nemennú zálohu a otestovať obnovu.", 6_500, "ransomware"),
    ("SIM-009", "OT-01", "Výrobné terminály používajú spoločný účet", "Vysoká", "Zaviesť osobné účty a evidenciu prístupov k terminálom.", 2_200, "vpn"),
    ("SIM-010", "NET-02", "Pravidlá medzi kanceláriou a výrobou sú príliš široké", "Kritická", "Obmedziť komunikáciu medzi výrobnou a kancelárskou sieťou.", 4_800, "vpn"),
    ("SIM-011", "NB-01", "Dva notebooky nemajú šifrovaný disk", "Stredná", "Zapnúť šifrovanie diskov a bezpečne uložiť obnovovacie kľúče.", 600, "loss"),
    ("SIM-012", "SRV-02", "Databázový servisný účet má nadmerné oprávnenia", "Vysoká", "Obmedziť servisný účet na potrebné operácie a rotovať heslo.", 1_800, "portal"),
    ("SIM-013", "SRV-04", "Neaktívne účty bývalých zamestnancov", "Stredná", "Zablokovať neaktívne účty a zaviesť kontrolu odchodov.", 500, "phishing"),
    ("SIM-014", "OT-02", "Nezdokumentované servisné prístupy dodávateľa", "Vysoká", "Zaviesť schvaľované časovo obmedzené servisné prístupy.", 2_800, "vpn"),
]

SCENARIOS = {
    "portal": {"title": "Únik zákaziek zo zákazníckeho portálu", "asset": "WEB-02", "finding": "SIM-001", "frequency": .35,
               "description": "V simulácii útočník cez nedostatočnú kontrolu oprávnení získa prístup k cudzím zákazkám a ich exportom.",
               "input": {"aktor_typy": ["external"], "aktor_variety": ["external:Organized crime"], "akcia_typy": ["hacking"], "akcia_variety": ["hacking:Forced browsing"], "akcia_vektory": ["hacking:Web application"], "motiv": ["Financial"], "sposob_odhalenia": ["internal"]}},
    "web": {"title": "Napadnutie verejného webu", "asset": "WEB-01", "finding": "SIM-002", "frequency": .25,
            "description": "Modelový útočník zneužije neaktualizovaný doplnok CMS a zmení obsah verejného webu.",
            "input": {"aktor_typy": ["external"], "akcia_typy": ["hacking"], "akcia_variety": ["hacking:Exploit vuln"], "akcia_vektory": ["hacking:Web application"], "atribut_integrity": True, "sposob_odhalenia": ["external"]}},
    "vpn": {"title": "Neoprávnený prístup cez VPN", "asset": "NET-01", "finding": "SIM-003", "frequency": .2,
            "description": "V simulácii sa útočník prihlási získaným heslom do VPN bez MFA. Ide o vstup do firemnej siete, nie o predikciu fyzickej poruchy výroby.",
            "input": {"aktor_typy": ["external"], "aktor_variety": ["external:Organized crime"], "akcia_typy": ["hacking"], "akcia_variety": ["hacking:Use of stolen creds"], "akcia_vektory": ["hacking:VPN"], "motiv": ["Financial"], "sposob_odhalenia": ["internal"]}},
    "ransomware": {"title": "Ransomvér na CAD pracovisku", "asset": "CAD-01", "finding": "SIM-004", "frequency": .3,
                   "description": "V simulácii sa ransomvér rozšíri vo firemnom prostredí a zasiahne pracovné alebo zálohované dáta. ML odhaduje iba rozsah prípadného úniku, nie čas odstávky.",
                   "input": {"aktor_typy": ["external"], "aktor_variety": ["external:Organized crime"], "akcia_typy": ["malware", "social"], "akcia_variety": ["malware:Ransomware", "social:Phishing"], "akcia_vektory": ["malware:Email attachment", "social:Email"], "atribut_availability": True, "motiv": ["Financial"], "sposob_odhalenia": ["internal"]}},
    "phishing": {"title": "Prevzatie firemnej poštovej schránky", "asset": "MAIL-01", "finding": "SIM-006", "frequency": .5,
                 "description": "Zamestnanec zadá heslo do podvodného prihlasovacieho formulára. V simulácii útočník získa prístup k jeho pošte.",
                 "input": {"aktor_typy": ["external"], "akcia_typy": ["social"], "akcia_variety": ["social:Phishing"], "akcia_vektory": ["social:Email"], "motiv": ["Financial"], "sposob_odhalenia": ["internal"]}},
    "export": {"title": "Nesprávne odoslaný export zákazníkov", "asset": "SRV-03", "finding": "SIM-007", "frequency": .4,
               "description": "V modelovej situácii zamestnanec odošle interný export nesprávnemu príjemcovi. Známe sú okolnosti, nie konečný rozsah úniku.",
               "input": {"aktor_typy": ["internal"], "aktor_variety": ["internal:End-user"], "akcia_typy": ["error"], "akcia_variety": ["error:Misdelivery"], "akcia_vektory": ["error:Carelessness"], "sposob_odhalenia": ["external"]}},
    "loss": {"title": "Strata služobného notebooku", "asset": "NB-01", "finding": "SIM-011", "frequency": .15,
             "description": "Zamestnanec v simulácii stratí služobný notebook. Nešifrovaný disk obsahuje firemné a osobné údaje.",
             "input": {"aktor_typy": ["internal"], "aktor_variety": ["internal:End-user"], "akcia_typy": ["error"], "akcia_variety": ["error:Loss"], "akcia_vektory": ["error:Carelessness"], "sposob_odhalenia": ["internal"]}},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS company_profile (id TEXT PRIMARY KEY, settings TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_assets (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
 address TEXT NOT NULL, technology TEXT NOT NULL, owner TEXT NOT NULL, criticality TEXT NOT NULL,
 model_asset TEXT NOT NULL, data_types TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_findings (
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES company_assets(id), title TEXT NOT NULL,
 severity TEXT NOT NULL, remediation TEXT NOT NULL, cost REAL NOT NULL CHECK(cost>=0), scenario TEXT NOT NULL,
 status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_cases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, scenario TEXT NOT NULL, asset_id TEXT NOT NULL REFERENCES company_assets(id),
 finding_id TEXT REFERENCES company_findings(id), title TEXT NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Na vyhodnotenie', simulated INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS company_assessments (
 assessment_id INTEGER PRIMARY KEY REFERENCES hodnotenia(id) ON DELETE CASCADE,
 company_id TEXT NOT NULL, asset_id TEXT NOT NULL REFERENCES company_assets(id),
 finding_id TEXT REFERENCES company_findings(id), case_id INTEGER REFERENCES company_cases(id),
 assumptions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def db():
    connection = op.connect()
    if not op.uses_azure_sql():
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA)
    try:
        with connection:
            if not connection.execute("SELECT 1 FROM company_profile WHERE id=?", (COMPANY_ID,)).fetchone():
                connection.execute("INSERT INTO company_profile VALUES (?,?)", (COMPANY_ID, json.dumps(PROFILE)))
                connection.cursor().executemany("INSERT INTO company_assets VALUES (?,?,?,?,?,?,?,?,?,?)",
                                       [(*asset[:-1], json.dumps(asset[-1])) for asset in ASSETS])
                connection.cursor().executemany("INSERT INTO company_findings VALUES (?,?,?,?,?,?,?,?,?,?)",
                                       [(f[0], f[1], f[2], f[3], f[4], f[5], f[6], "Otvorená", "Modelové zistenie; nejde o výsledok skenovania.", now()) for f in FINDINGS])
                connection.execute("INSERT INTO company_events(created_at,kind,detail) VALUES (?,?,?)", (now(), "Inicializácia", "Vytvorený profil simulovanej výrobnej firmy."))
            # Migration for the initial local simulation seed: notebook loss is a separate scenario.
            previous = connection.execute("SELECT title,scenario FROM company_findings WHERE id='SIM-011'").fetchone()
            if previous and previous["title"] == "Dva notebooky nemajú šifrovaný disk" and previous["scenario"] == "export":
                connection.execute("UPDATE company_findings SET scenario='loss' WHERE id='SIM-011'")
            yield connection
    finally:
        connection.close()


def profile():
    with db() as connection:
        return json.loads(connection.execute("SELECT settings FROM company_profile WHERE id=?", (COMPANY_ID,)).fetchone()[0])


def update_settings(budget, losses, cost_factor, horizon):
    if not 0 <= budget <= 10_000_000 or len(losses) != 3 or not 0 < losses[0] <= losses[1] <= losses[2] or not .01 <= cost_factor <= 10 or not 1 <= horizon <= 10:
        raise ValueError("Neplatný rozpočet alebo ekonomické predpoklady.")
    current = profile()
    current.update(budget=float(budget), losses=list(map(float, losses)), cost_factor=float(cost_factor), horizon=int(horizon))
    with db() as connection:
        connection.execute("UPDATE company_profile SET settings=? WHERE id=?", (json.dumps(current), COMPANY_ID))
        event(connection, "Nastavenia", "Upravený rozpočet alebo ekonomické predpoklady firmy.")


def event(connection, kind, detail):
    connection.execute("INSERT INTO company_events(created_at,kind,detail) VALUES (?,?,?)", (now(), kind, detail))


def read_frame(sql, connection, params=None):
    if op.uses_azure_sql():
        cursor = connection.execute(sql, params or ())
        return pd.DataFrame.from_records(
            [tuple(row) for row in cursor.fetchall()], columns=[column[0] for column in cursor.description]
        )
    return pd.read_sql_query(sql, connection, params=params)


def row_dict(row):
    return dict(row._mapping) if op.uses_azure_sql() else dict(row)


def assets():
    with db() as connection:
        return read_frame("SELECT * FROM company_assets ORDER BY category,id", connection)


def asset(asset_id):
    with db() as connection:
        row = connection.execute("SELECT * FROM company_assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("Aktívum neexistuje.")
        return row_dict(row)


def findings():
    with db() as connection:
        return read_frame("SELECT f.*,a.name AS asset_name,a.category FROM company_findings f JOIN company_assets a ON a.id=f.asset_id ORDER BY f.id", connection)


def finding(finding_id):
    with db() as connection:
        row = connection.execute("SELECT * FROM company_findings WHERE id=?", (finding_id,)).fetchone()
        if row is None:
            raise ValueError("Zraniteľnosť neexistuje.")
        return row_dict(row)


def set_finding_status(finding_id, status, note=""):
    if status not in STATUSES:
        raise ValueError("Neplatný stav zraniteľnosti.")
    finding(finding_id)
    with db() as connection:
        connection.execute("UPDATE company_findings SET status=?,note=?,updated_at=? WHERE id=?", (status, note[:2000], now(), finding_id))
        event(connection, "Zraniteľnosť", f"{finding_id}: {status}. {note[:200]}")


def add_asset(name, category, quantity, address, technology, owner, criticality, model_asset):
    if not name.strip() or quantity < 1 or model_asset not in op.choices()["aktivum_variety"] or criticality not in SEVERITIES:
        raise ValueError("Vyplňte názov, platný počet, kritickosť a typ aktíva.")
    with db() as connection:
        number = connection.execute("SELECT COUNT(*) FROM company_assets").fetchone()[0] + 1
        asset_id = f"CUSTOM-{number:03d}"
        while connection.execute("SELECT 1 FROM company_assets WHERE id=?", (asset_id,)).fetchone():
            number += 1
            asset_id = f"CUSTOM-{number:03d}"
        connection.execute("INSERT INTO company_assets VALUES (?,?,?,?,?,?,?,?,?,?)", (asset_id, name.strip()[:150], category, int(quantity), address[:200], technology[:200], owner[:150], criticality, model_asset, json.dumps(["Internal"])))
        event(connection, "Aktívum", f"Pridané {asset_id}: {name.strip()[:150]}")
        return asset_id


def add_finding(asset_id, title, severity, remediation, cost, scenario):
    asset(asset_id)
    if not title.strip() or not remediation.strip() or severity not in SEVERITIES or cost < 0 or scenario not in SCENARIOS:
        raise ValueError("Vyplňte názov, závažnosť, návrh opravy, scenár a nezápornú cenu.")
    with db() as connection:
        number = connection.execute("SELECT COUNT(*) FROM company_findings").fetchone()[0] + 1
        finding_id = f"SIM-{number:03d}"
        while connection.execute("SELECT 1 FROM company_findings WHERE id=?", (finding_id,)).fetchone():
            number += 1
            finding_id = f"SIM-{number:03d}"
        connection.execute("INSERT INTO company_findings VALUES (?,?,?,?,?,?,?,?,?,?)", (finding_id, asset_id, title.strip()[:200], severity, remediation.strip()[:2000], float(cost), scenario, "Otvorená", "Ručne pridané modelové zistenie.", now()))
        event(connection, "Zraniteľnosť", f"Pridaná {finding_id}: {title.strip()[:200]}")
        return finding_id


def incident_input(asset_id, scenario=None):
    a = asset(asset_id)
    incident = op.default_input()
    incident.update(odvetvie="Výroba", velkost_organizacie="malá", krajina="iná",
                    aktivum_variety=[a["model_asset"]], typy_dat=json.loads(a["data_types"]))
    if scenario:
        incident.update(json.loads(json.dumps(SCENARIOS[scenario]["input"])))
    return incident


def start_simulation(scenario_id, finding_id=None):
    if scenario_id not in SCENARIOS:
        raise ValueError("Scenár neexistuje.")
    scenario = SCENARIOS[scenario_id]
    f = finding(finding_id or scenario["finding"])
    if f["scenario"] != scenario_id:
        raise ValueError("Zraniteľnosť nepatrí k scenáru.")
    if f["status"] == "Odstránená":
        raise ValueError("Zraniteľnosť je odstránená. Vyberte otvorené zistenie alebo ho najprv znovu otvorte.")
    with db() as connection:
        output = " OUTPUT INSERTED.id" if op.uses_azure_sql() else ""
        cursor = connection.execute(f"INSERT INTO company_cases(scenario,asset_id,finding_id,title,created_at){output} VALUES (?,?,?,?,?)", (scenario_id, f["asset_id"], f["id"], scenario["title"], now()))
        case_id = int(cursor.fetchone()[0]) if op.uses_azure_sql() else cursor.lastrowid
        event(connection, "Simulácia", f"Incident č. {case_id}: {scenario['title']} ({f['asset_id']}).")
    return {"id": case_id, "scenario": scenario_id, "asset_id": f["asset_id"], "finding_id": f["id"],
            "title": scenario["title"], "description": scenario["description"], "frequency": scenario["frequency"],
            "input": incident_input(f["asset_id"], scenario_id)}


def assess(incident, frequency=None):
    company = profile()
    if (incident.get("odvetvie"), incident.get("velkost_organizacie"), incident.get("krajina")) != ("Výroba", "malá", "iná"):
        raise ValueError("Hodnotenie musí používať profil firmy HronTech.")
    errors = op.validate(incident)
    if errors:
        raise ValueError(" ".join(errors))
    if frequency is not None and not 0 <= frequency <= 100:
        raise ValueError("Frekvencia musí byť od 0 do 100.")
    result = op.assess(incident, frequency, loss=company["losses"], cost_factor=company["cost_factor"], horizon=company["horizon"])
    result["company"] = company["name"]
    result["assumptions"] = {k: company[k] for k in ["losses", "cost_factor", "horizon", "budget"]}
    result["within_budget"] = result["cena_opatrenia"] <= company["budget"]
    return result


def assess_and_save(incident, asset_id, frequency=None, name="", finding_id=None, case_id=None, source="aplikácia", actual_impact=None):
    a = asset(asset_id)
    if incident.get("aktivum_variety") != [a["model_asset"]]:
        raise ValueError("Typ aktíva v incidente nezodpovedá vybranému firemnému aktívu.")
    if finding_id and finding(finding_id)["asset_id"] != asset_id:
        raise ValueError("Zraniteľnosť nepatrí vybranému aktívu.")
    if actual_impact is not None and actual_impact not in op.LABELS:
        raise ValueError("Neplatný skutočný dopad.")
    result = assess(incident, frequency)
    with db() as connection:
        if case_id is not None:
            case = connection.execute("SELECT * FROM company_cases WHERE id=?", (case_id,)).fetchone()
            if case is None or case["asset_id"] != asset_id or case["finding_id"] != finding_id:
                raise ValueError("Incident nezodpovedá vybranému aktívu a zraniteľnosti.")
        record_id = op.save_assessment(incident, result, source, name, actual_impact=actual_impact, connection=connection)
        connection.execute("INSERT INTO company_assessments VALUES (?,?,?,?,?,?)", (record_id, COMPANY_ID, asset_id, finding_id, case_id, json.dumps(result["assumptions"])))
        if case_id:
            connection.execute("UPDATE company_cases SET status='Vyhodnotený' WHERE id=?", (case_id,))
        event(connection, "Hodnotenie", f"Hodnotenie č. {record_id}: {a['name']}, {result['predikovany_dopad']}, {result['opatrenie']}.")
    result.update(asset_id=asset_id, asset_name=a["name"], finding_id=finding_id, case_id=case_id)
    return record_id, result


def assessments():
    with db() as connection:
        return read_frame("SELECT h.*,a.name AS asset_name,c.asset_id,c.finding_id,c.case_id FROM hodnotenia h JOIN company_assessments c ON c.assessment_id=h.id JOIN company_assets a ON a.id=c.asset_id WHERE c.company_id=? ORDER BY h.ocakavana_strata DESC,h.id DESC", connection, params=(COMPANY_ID,))


def cases():
    with db() as connection:
        return read_frame("SELECT c.*,a.name AS asset_name FROM company_cases c JOIN company_assets a ON a.id=c.asset_id ORDER BY c.id DESC", connection)


def events():
    with db() as connection:
        query = "SELECT TOP 40 * FROM company_events ORDER BY id DESC" if op.uses_azure_sql() else "SELECT * FROM company_events ORDER BY id DESC LIMIT 40"
        return read_frame(query, connection)


def risk_register():
    """One non-overlapping planning scenario per authored incident family, not per finding."""
    rows = []
    all_findings = findings()
    for scenario_id, scenario in SCENARIOS.items():
        open_findings = all_findings[(all_findings.scenario == scenario_id) & (all_findings.status != "Odstránená")]
        if open_findings.empty:
            continue
        result = assess(incident_input(scenario["asset"], scenario_id), scenario["frequency"])
        rows.append({"scenár": scenario["title"], "typ": scenario_id, "otvorené zistenia": len(open_findings),
                     "frekvencia": scenario["frequency"], "dopad": result["predikovany_dopad"],
                     "P(vysoký)": result["pravdepodobnosti"]["vysoký"], "riziko (€)": result["ocakavana_strata"],
                     "opatrenie": result["opatrenie"], "cena (€)": result["cena_opatrenia"],
                     "zostane (€)": result["zostavajuca_strata"], "prínos (€)": result["cisty_prinos"],
                     "CIS": result["opatrenia_cis"], "efektivita": result["cisty_prinos"] / max(result["cena_opatrenia"], 1)})
    return pd.DataFrame(rows).sort_values("efektivita", ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def budget_plan(budget, register=None):
    if not 0 <= budget <= 10_000_000:
        raise ValueError("Neplatný rozpočet.")
    register = risk_register() if register is None else register
    monitoring = op.MONITORING_COST * profile()["cost_factor"]
    baseline = monitoring * len(register)
    if budget < baseline:
        return {"baseline": baseline, "affordable": False, "spent": 0., "remaining": budget, "selected": pd.DataFrame()}
    remaining, selected = budget - baseline, []
    for _, row in register.iterrows():
        extra = max(0., row["cena (€)"] - monitoring)
        if row["prínos (€)"] > 0 and extra <= remaining:
            entry = row.to_dict()
            entry["navýšenie (€)"] = extra
            selected.append(entry)
            remaining -= extra
    return {"baseline": baseline, "affordable": True, "spent": budget - remaining, "remaining": remaining,
            "selected": pd.DataFrame(selected)}
