"""Generate fictional HronTech incidents through the company REST API.

python simulacia.py --pocet 10 --interval 3 --seed 67
No network traffic is scanned or attacked. No ground-truth impact is invented.
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

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def parse_args():
    parser = argparse.ArgumentParser(description="Generátor simulovaných incidentov výrobnej firmy HronTech.")
    parser.add_argument("--api", default=os.environ.get("SIMULACIA_API", "http://127.0.0.1:8000"))
    parser.add_argument("--interval", type=float, default=3.0, help="Priemerný interval v sekundách.")
    parser.add_argument("--rozptyl", type=float, default=.5, help="Relatívna odchýlka intervalu, od 0 do menej ako 1.")
    parser.add_argument("--pocet", type=int, default=0, help="Počet incidentov, 0 znamená do zastavenia Ctrl+C.")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.interval <= 0 or not 0 <= args.rozptyl < 1 or args.pocet < 0:
        parser.error("Interval musí byť kladný, rozptyl v <0,1) a počet nezáporný.")
    return args


def call(method, url, body=None, timeout=30):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json; charset=utf-8"})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(api, attempts=30):
    for attempt in range(attempts):
        try:
            call("GET", f"{api}/api/firma", timeout=5)
            return
        except (urllib.error.URLError, OSError) as error:
            if attempt == 0:
                print(f"Čakám na firemné API {api}: {error}", flush=True)
            time.sleep(2)
    raise RuntimeError("Firemné API neodpovedá. Spustite uvicorn api:app --port 8000.")


def incident_body(case):
    return {**case["input"], "asset_id": case["asset_id"], "finding_id": case["finding_id"],
            "case_id": case["id"], "frekvencia": case["frequency"], "nazov": case["title"], "zdroj": "simulácia"}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    api, rng = args.api.rstrip("/"), random.Random(args.seed)
    try:
        wait_for_api(api)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    sent = failures = 0
    print(f"Simulácia HronTech: interval ~{args.interval:g} s. Zastavenie Ctrl+C.", flush=True)
    try:
        while not args.pocet or sent < args.pocet:
            try:
                findings = call("GET", f"{api}/api/firma/zranitelnosti")
                active = [finding for finding in findings if finding["status"] != "Odstránená"]
                if not active:
                    print("Žiadne otvorené zistenia pre simuláciu. Generátor sa zastavuje.", flush=True)
                    break
                finding = rng.choice(active)
                case = call("POST", f"{api}/api/firma/simulacia", {"scenario": finding["scenario"], "finding_id": finding["id"]})
                result = call("POST", f"{api}/api/hodnotenie", incident_body(case))
                sent += 1
                failures = 0
                print(f"{datetime.now():%H:%M:%S} #{result['id']} | {result['asset_name']} | "
                      f"{result['predikovany_dopad']} | {result['ocakavana_strata']:,.0f} EUR/rok | {result['opatrenie']}", flush=True)
            except (urllib.error.URLError, OSError, KeyError, ValueError) as error:
                failures += 1
                detail = error.read().decode("utf-8", "replace") if isinstance(error, urllib.error.HTTPError) else str(error)
                print(f"Požiadavka zlyhala: {detail}", file=sys.stderr, flush=True)
                if failures >= 3:
                    print("Tri po sebe idúce chyby. Generátor sa zastavuje.", file=sys.stderr)
                    return 1
            if not args.pocet or sent < args.pocet:
                time.sleep(args.interval * rng.uniform(1 - args.rozptyl, 1 + args.rozptyl))
    except KeyboardInterrupt:
        pass
    print(f"Odoslané a uložené incidenty: {sent}. Dopad je predikovaný; skutočný rozsah pri simulácii nepoznáme.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
