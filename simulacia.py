"""Simulácia sledovania siete: generátor posiela testovacie incidenty z VCDB na REST API.

Každých pár sekúnd vyberie náhodný incident z testovacej časti dát (rovnaký ako tlačidlo
Náhodný testovací incident v aplikácii) a pošle ho na POST /api/hodnotenie. API ho vyhodnotí
a uloží do databázy, odkiaľ ho záložka Živé sledovanie v aplikácii hneď zobrazí.

Spustenie (API musí bežať):
    python simulacia.py                      # každé 3 s, kým ho nezastavíte (Ctrl+C)
    python simulacia.py --interval 1 --pocet 50
    python simulacia.py --api http://127.0.0.1:8000 --seed 67
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

import opatrenia as op

# Volania na localhost nesmú ísť cez systémovú proxy
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def parse_args():
    parser = argparse.ArgumentParser(description="Posiela testovacie incidenty z VCDB na REST API ako simuláciu sledovania siete.")
    # 127.0.0.1 namiesto localhost: na Windowse sa localhost najprv skúša cez IPv6 a každé volanie by trvalo ~2 s
    parser.add_argument("--api", default=os.environ.get("SIMULACIA_API", "http://127.0.0.1:8000"),
                        help="adresa API (predvolene http://127.0.0.1:8000 alebo premenná SIMULACIA_API)")
    parser.add_argument("--interval", type=float, default=3.0, help="priemerný počet sekúnd medzi incidentmi (predvolene 3)")
    parser.add_argument("--rozptyl", type=float, default=0.5,
                        help="náhodná odchýlka intervalu ako podiel z neho, 0 = presne pravidelne (predvolene 0,5)")
    parser.add_argument("--pocet", type=int, default=0, help="koľko incidentov poslať, 0 = bez obmedzenia (predvolene 0)")
    parser.add_argument("--seed", type=int, default=None, help="seed pre opakovateľné poradie incidentov")
    args = parser.parse_args()
    if args.interval <= 0 or not 0 <= args.rozptyl < 1 or args.pocet < 0:
        parser.error("interval musí byť kladný, rozptyl v intervale <0, 1) a počet nezáporný")
    return args


def call(method, url, body=None, timeout=30):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(api, attempts=30):
    """Počká, kým API odpovedá, aby sa generátor dal spustiť naraz s ním."""
    for attempt in range(attempts):
        try:
            call("GET", f"{api}/api/moznosti", timeout=5)
            return
        except (urllib.error.URLError, OSError) as error:
            if attempt == 0:
                print(f"Čakám na API {api} … ({error})", flush=True)
            time.sleep(2)
    sys.exit(f"API {api} neodpovedá. Spustite ho príkazom: uvicorn api:app --port 8000")


def incident_body(sample):
    """Telo požiadavky POST /api/hodnotenie z testovacieho incidentu."""
    return {
        **sample["vstup"],
        "nazov": f"VCDB #{sample['zaznam_id']}",
        "zdroj": "simulácia",
        "skutocny_dopad": sample["skutocny_dopad"],
    }


def euro(value):
    return f"{value:,.0f}".replace(",", " ") + " €"


def main():
    # Výpis do súboru alebo do konzoly s inou znakovou sadou nesmie spadnúť na znakoch ✓ a ✗
    if sys.stdout.isatty():
        sys.stdout.reconfigure(errors="replace")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    api = args.api.rstrip("/")
    wait_for_api(api)
    rng = random.Random(args.seed)
    print(f"Simulácia beží: incident každých ~{args.interval:g} s na {api}/api/hodnotenie. Zastavenie: Ctrl+C", flush=True)

    sent = hits = 0
    try:
        while not args.pocet or sent < args.pocet:
            sample = op.random_test_incident(rng.randrange(2**32))
            try:
                result = call("POST", f"{api}/api/hodnotenie", incident_body(sample))
            except urllib.error.HTTPError as error:
                print(f"Incident VCDB #{sample['zaznam_id']} odmietnutý ({error.code}): {error.read().decode('utf-8', 'replace')}",
                      flush=True)
            except (urllib.error.URLError, OSError) as error:
                print(f"API neodpovedá ({error}), skúsim znova.", flush=True)
            else:
                sent += 1
                hit = result["predikovany_dopad"] == sample["skutocny_dopad"]
                hits += hit
                print(f"{datetime.now():%H:%M:%S}  #{result['id']:<5} {result['odvetvie'][:22]:<22} "
                      f"{result['vzor_utoku'][:26]:<26} dopad {result['predikovany_dopad']:<7} "
                      f"(skutočný {sample['skutocny_dopad']:<7} {'✓' if hit else '✗'})  "
                      f"strata {euro(result['ocakavana_strata']):>11}/rok  → {result['opatrenie']}", flush=True)
            if not args.pocet or sent < args.pocet:
                time.sleep(args.interval * rng.uniform(1 - args.rozptyl, 1 + args.rozptyl))
    except KeyboardInterrupt:
        pass
    if sent:
        print(f"\nOdoslané incidenty: {sent}, predikovaný dopad sa zhodol so skutočným v {hits / sent:.0%} prípadov.")


if __name__ == "__main__":
    main()
