"""Integračná kontrola verejného HTTP API a vykreslenia Streamlitu cez WebSocket."""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from frontend import PAGES

import requests
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect

BASE = "https://safetyfirst-hrontech-54c15147.azurewebsites.net"
session = requests.Session()
for path in ["/", "/_stcore/health", "/api/moznosti", "/api/register", "/api/hodnotenia", "/api/firma", "/api/firma/aktiva", "/api/firma/zranitelnosti", "/api/firma/incidenty", "/api/firma/scenare", "/docs", "/openapi.json"]:
    response = session.get(BASE + path, timeout=60)
    response.raise_for_status()
    print(path, response.status_code, flush=True)

cookies = "; ".join(f"{cookie.name}={cookie.value}" for cookie in session.cookies)
protocols = ["streamlit"]
token = session.cookies.get("_streamlit_xsrf")
if token:
    protocols.append(token)
with connect(BASE.replace("https:", "wss:") + "/_stcore/stream",
             origin=BASE, subprotocols=protocols,
             additional_headers={"Cookie": cookies},
             open_timeout=60, close_timeout=5, max_size=16 * 1024 * 1024) as websocket:
    radio_id = None
    pages = ["Firma", "Simulácia", "Živé sledovanie", "Nové hodnotenie", "Uložené hodnotenia", "Prehľad", "Register rizík", "Predpoklady"]
    for index, page in enumerate(pages):
        request = BackMsg()
        request.rerun_script.query_string = ""
        if radio_id:
            state = request.rerun_script.widget_states.widgets.add()
            state.id = radio_id
            state.string_value = page
        websocket.send(request.SerializeToString())
        deadline = time.monotonic() + 90
        errors = []
        rendered_radio = False
        rendered_title = False
        while time.monotonic() < deadline:
            message = ForwardMsg()
            message.ParseFromString(websocket.recv(timeout=60))
            if message.HasField("delta") and message.delta.HasField("new_element"):
                element = message.delta.new_element
                if element.HasField("exception"):
                    errors.append(element.exception.message)
                if element.HasField("html") and PAGES[page][0] in element.html.body:
                    rendered_title = True
                if element.HasField("radio") and element.radio.label == "Pracovný priestor":
                    radio_id = element.radio.id
                    assert list(element.radio.options) == pages
                    rendered_radio = True
            if message.HasField("script_finished") and rendered_radio:
                assert not errors, (page, errors)
                assert rendered_title, (page, "Chyba nadpis stranky")
                print("Verejna stranka cez WebSocket OK:", page, flush=True)
                break
        else:
            raise TimeoutError("Streamlit nedokoncil stranku " + page)
