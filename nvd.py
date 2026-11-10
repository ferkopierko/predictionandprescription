"""Klient verejného API databázy NVD (CVE API 2.0)."""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
USER_AGENT = "cve-severity-student-project/1.0"
PAGE_SIZE = 2000
MAX_WINDOW = timedelta(days=120)
API_KEY = os.environ.get("NVD_API_KEY", "")
# Bez kľúča povoľuje NVD 5 požiadaviek za 30 sekúnd, s kľúčom 50
REQUEST_PAUSE = 0.8 if API_KEY else 6.5
LABELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _timestamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _get(params, retries=6):
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": USER_AGENT}
    if API_KEY:
        headers["apiKey"] = API_KEY

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in {403, 408, 429, 500, 502, 503, 504}:
                raise
            if attempt == retries - 1:
                raise
            time.sleep(min(30 * 2**attempt, 300))
    raise RuntimeError("NVD neodpovedá")


def fetch_window(start, end, field="pub"):
    """Vráti záznamy CVE v okne najviac 120 dní. Pole je `pub` alebo `lastMod`."""
    if end - start > MAX_WINDOW:
        raise ValueError("NVD povoľuje okno najviac 120 dní")

    records, index = [], 0
    while True:
        page = _get({
            f"{field}StartDate": _timestamp(start),
            f"{field}EndDate": _timestamp(end),
            "resultsPerPage": PAGE_SIZE,
            "startIndex": index,
        })
        records.extend(parse_record(item["cve"]) for item in page["vulnerabilities"])
        index += page["resultsPerPage"]
        if index >= page["totalResults"] or page["resultsPerPage"] == 0:
            return records
        time.sleep(REQUEST_PAUSE)


def _severity_v3(metrics):
    """Vyberie závažnosť CVSS v3, prednostne hodnotenie samotného NVD."""
    for version in ("cvssMetricV31", "cvssMetricV30"):
        candidates = sorted(metrics.get(version, []), key=lambda item: item.get("type") != "Primary")
        for item in candidates:
            severity = item.get("cvssData", {}).get("baseSeverity")
            if severity in LABELS:
                return severity, item.get("type", "")
    return None, ""


def parse_record(cve):
    description = next((d["value"].strip() for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
    cwe_ids = []
    for weakness in cve.get("weaknesses", []):
        for entry in weakness.get("description", []):
            for cwe in re.findall(r"CWE-\d+", entry.get("value", "")):
                if cwe not in cwe_ids:
                    cwe_ids.append(cwe)
    severity, label_type = _severity_v3(cve.get("metrics", {}))
    return {
        "cve_id": cve["id"],
        "published": cve.get("published", ""),
        "last_modified": cve.get("lastModified", ""),
        "vuln_status": cve.get("vulnStatus", ""),
        "source": cve.get("sourceIdentifier", ""),
        "description": description,
        "cwe_text": " ".join(cwe_ids),
        "severity": severity,
        "label_type": label_type,
    }
