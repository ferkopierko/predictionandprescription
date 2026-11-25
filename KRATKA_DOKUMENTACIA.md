# Krátka dokumentácia: predikcia a preskripcia rizík bezpečnostných incidentov

**Predmet:** AISPU, zadanie č. 2: Prediktívna a preskriptívna údržba, zameranie Threat Modeling and Risk Assessment.
Podrobný opis je v [DOKUMENTACIA.md](DOKUMENTACIA.md), vysvetlenie jednotlivých častí v [VYSVETLENIE.md](VYSVETLENIE.md).

## Čo projekt robí

Modul informačného systému, ktorý pre bezpečnostný incident:

1. **predikuje dopad** (`nízky`, `stredný`, `vysoký`) z informácií známych hneď po jeho odhalení,
2. **odporučí opatrenie** (akceptovať a monitorovať, prevencia, detekcia a reakcia, komplexná ochrana) s konkrétnymi opatreniami CIS Controls v8 podľa rizika, nákladov, času zavedenia a priority.

Analógia s údržbou: incident je porucha, vzor útoku typ poruchy, dopad závažnosť poruchy a opatrenia CIS zásahy údržby.

## Dáta

**VERIS Community Database (VCDB)**: 10 047 verejne známych incidentov (licencia CC BY-SA 4.0), verzia pripnutá na commit `5ebf2f5` a overená kontrolným súčtom. Každý incident opisuje aktéra, spôsob útoku, aktívum a narušený atribút, pri úniku dát aj počet záznamov. Notebook [priprava_dat.ipynb](priprava_dat.ipynb) dáta vyčistí (duplikáty, nepotvrdené a nevhodné incidenty), rozbalí do tabuľky a priradí vzory útokov a opatrenia CIS.

## Predikcia

Notebook [predikcia.ipynb](predikcia.ipynb) porovnáva **logistickú regresiu** a **LightGBM**. Dáta sa delia podľa zdroja incidentu, aby takmer rovnaké incidenty neboli v tréningu aj v teste. Vstupom nie sú údaje, ktoré by prezradili výsledok (popis, počet záznamov).

| Metrika (test, 1 052 incidentov) | Triviálny model | Logistická regresia | LightGBM |
| --- | ---: | ---: | ---: |
| Macro F1 | 0,191 | 0,656 | **0,660** |
| Accuracy | 0,401 | 0,652 | **0,659** |
| Recall `vysoký` | 0,000 | **0,785** | 0,767 |
| Log loss | 1,079 | 0,759 | **0,735** |

V aplikácii sa používa LightGBM, lebo má lepšie kalibrované pravdepodobnosti, z ktorých sa počíta riziko.

## Preskripcia

Notebook [preskriptivna_udrzba.ipynb](preskriptivna_udrzba.ipynb) vyhodnotí 48 scenárov (6 odvetví × 8 vzorov útokov). Pre každý vyberie opatrenie s najnižšími celkovými ročnými nákladmi:

```
celkové_náklady = cena_opatrenia + očakávaná_strata × (zostatok po opatrení, upravený o čas zavedenia)
očakávaná_strata = frekvencia × Σ P(dopad) × strata pri dopade
```

Pri obmedzenom rozpočte sa opatrenia zoradia podľa čistého prínosu na euro. Rozhodovanie podľa predikovaného dopadu stojí ročne 589 913 € na organizáciu, len o 1 520 € viac ako teoretické optimum a o 17,7 % menej ako najlepšia pevná stratégia. Ceny a účinnosť opatrení sú predpoklady, dataset ich neobsahuje.

## Aplikácia a integrácia

| Súčasť | Súbor | Úloha |
| --- | --- | --- |
| Frontend | [app.py](app.py) | Streamlit, <http://localhost:8501> |
| REST API | [api.py](api.py) | FastAPI, <http://localhost:8000/docs> |
| Logika | [opatrenia.py](opatrenia.py) | predikcia, výber opatrenia, databáza |
| Simulácia | [simulacia.py](simulacia.py) | generátor incidentov pre živé sledovanie |
| Databáza | SQLite, tabuľka `hodnotenia` | spoločná pre aplikáciu aj API |

Záložky aplikácie: **Nové hodnotenie** (formulár incidentu), **Uložené hodnotenia**, **Prehľad** (grafy, obnovujú sa každých 5 s), **Živé sledovanie**, **Register rizík** a **Predpoklady**.

## Simulácia sledovania siete

Namiesto ručného vypĺňania formulára simuluje sledovanie siete generátor [simulacia.py](simulacia.py):

```
simulacia.py ──POST /api/hodnotenie──► api.py ──► opatrenia.py (model + opatrenie) ──► SQLite
                                                                                         │
                                      app.py, záložka Živé sledovanie (obnova každé 2 s) ◄┘
```

1. Generátor každých ~3 s (s náhodnou odchýlkou) vyberie incident z **testovacej časti VCDB**, ktorú model pri tréningu nevidel.
2. Pošle ho na `POST /api/hodnotenie` s poľom `zdroj: "simulácia"` a so skutočným dopadom z dát (`skutocny_dopad`). Model skutočný dopad nepoužíva, slúži iba na porovnanie.
3. API incident vyhodnotí a uloží. Generátor vypíše riadok s predikovaným a skutočným dopadom, očakávanou stratou a opatrením.
4. Záložka **Živé sledovanie** ukazuje, či generátor beží, ukazovatele (počet incidentov, vysoký dopad, zhoda so skutočným dopadom, očakávaná strata), tabuľku posledných incidentov so zvýraznením nových a grafy straty v čase a vzorov útokov. Dá sa prepnúť na všetky zdroje a simulované hodnotenia vymazať.

Parametre generátora: `--interval` (sekundy medzi incidentmi), `--rozptyl` (náhodná odchýlka), `--pocet` (0 = bez obmedzenia), `--seed` (opakovateľné poradie), `--api` (adresa API).

## Spustenie

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace priprava_dat.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia.ipynb
jupyter nbconvert --to notebook --execute --inplace preskriptivna_udrzba.ipynb

# tri okná terminálu
streamlit run app.py --server.address localhost
uvicorn api:app --port 8000
python simulacia.py
```

S Dockerom: `docker compose --profile simulacia up -d --build` spustí aplikáciu, API aj generátor. Bez `--profile simulacia` sa generátor nespustí.

## Obmedzenia

- VCDB obsahuje iba verejne známe incidenty a 73 % obetí je z USA.
- Dopad je meraný počtom uniknutých záznamov, nie peniazmi. Straty, ceny a účinnosť opatrení sú predpoklady.
- Približne 4 z 10 predikcií vysokého dopadu sú zbytočný poplach (precision 0,59).
- Simulácia posiela už známe incidenty z VCDB, nie skutočnú sieťovú prevádzku. Ukazuje, ako by sa modul napojil na systém sledovania (SIEM), ktorý by incidenty posielal na API.
