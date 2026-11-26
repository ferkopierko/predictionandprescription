"""Potvrdí, že web skutočne obsluhuje očakávaný Git commit."""

import argparse
import json
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--revision", required=True)
args = parser.parse_args()
base = args.url.rstrip("/")

for attempt in range(40):
    try:
        request = urllib.request.Request(base + "/health", headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=15) as response:
            health = json.load(response)
        if health.get("status") == "ok" and health.get("revision") == args.revision:
            break
    except (OSError, urllib.error.HTTPError, ValueError):
        pass
    print(f"Cakam na commit {args.revision[:7]}, pokus {attempt + 1}/40", flush=True)
    time.sleep(10)
else:
    raise SystemExit("Web nepotvrdil nasadeny commit")

for attempt in range(3):
    try:
        with urllib.request.urlopen(base + "/api/firma", timeout=90) as response:
            profile = json.load(response)
        assert profile["id"] == "hrontech", profile
        print(f"Nasadenie overene: {args.revision}, {profile['name']}")
        break
    except (OSError, urllib.error.HTTPError):
        if attempt == 2:
            raise
        time.sleep(10)
