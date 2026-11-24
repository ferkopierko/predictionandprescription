# Threat Modeling and Risk Assessment

Stručný prehľad je v [KRATKA_DOKUMENTACIA.md](KRATKA_DOKUMENTACIA.md), podrobný opis riešenia v [DOKUMENTACIA.md](DOKUMENTACIA.md) a vysvetlenie, ako jednotlivé časti fungujú, v [VYSVETLENIE.md](VYSVETLENIE.md).

## Dataset

**VERIS Community Database (VCDB)**, 10 047 verejne známych bezpečnostných incidentov zapísaných v štandarde VERIS.

- Odkaz: <https://github.com/vz-risk/VCDB>, verzia pripnutá na commit `5ebf2f5` z 10. 11. 2026
- Licencia: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), autor Verizon RISK Team a prispievatelia VCDB

Každý incident opisuje celý model hrozby: kto útočil (actor), akým spôsobom (action), na aké aktívum (asset) a čo narušil (attribute). Pri úniku dát uvádza aj počet uniknutých záznamov. Preto sa z neho dá odhadnúť pravdepodobnosť aj dopad scenára hrozby.

Samotné dáta nie sú v repozitári. `vcdb_data.py` ich stiahne do `data/raw/vcdb/` a overí ich kontrolný súčet.

## Príprava dát

Notebook [priprava_dat.ipynb](priprava_dat.ipynb) dáta vyčistí, rozbalí do tabuľky podľa modelu hrozby, analyzuje ich a vytvorí 2 vizualizácie. Priradí incidentom vzor útoku a vzorom opatrenia CIS Controls v8. Grafy sú v priečinku [figures/](figures/).

## Predikčná analýza

Notebook [predikcia.ipynb](predikcia.ipynb) porovnáva logistickú regresiu a LightGBM pri odhade dopadu incidentu (`nízky`, `stredný`, `vysoký`) z informácií známych hneď po jeho odhalení. Incidenty z rovnakého zdroja sú vždy v tej istej časti dát. Model sa ukladá do `data/processed/model_dopad_vcdb.joblib` a príprava jeho znakov je v `vcdb_model.py`.

Notebook [predikcia_70_30.ipynb](predikcia_70_30.ipynb) rieši zjednodušenú úlohu so zlúčenými triedami `nízky` a `stredný` a náhodným rozdelením dát 70:30 so seedom 67.

## Preskriptívna analýza

Notebook [preskriptivna_udrzba.ipynb](preskriptivna_udrzba.ipynb) pre 48 scenárov rizika (6 odvetví × 8 vzorov útokov) vyberá jedno zo 4 opatrení: akceptovať a monitorovať, prevencia, detekcia a reakcia, alebo komplexná ochrana. Rozhodnutie zohľadňuje riziko, náklady, čas zavedenia a prioritu. Ceny a účinnosť opatrení sú predpoklady uvedené v notebooku, lebo dataset ich neobsahuje.

## Spustenie

Potrebný je Python 3.11 alebo novší (projekt je odskúšaný s 3.13).

**macOS**

```bash
brew install python@3.13 libomp   # ak chýba novší Python alebo OpenMP pre LightGBM
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace priprava_dat.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia_70_30.ipynb
jupyter nbconvert --to notebook --execute --inplace preskriptivna_udrzba.ipynb
```

Systémový `python3` na macOS je často iba 3.9, preto treba vytvoriť prostredie príkazom `python3.13`. LightGBM na Macu potrebuje knižnicu OpenMP (`libomp`), bez nej notebook `predikcia.ipynb` zlyhá s chybou `Library not loaded: libomp.dylib`.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace priprava_dat.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia_70_30.ipynb
jupyter nbconvert --to notebook --execute --inplace preskriptivna_udrzba.ipynb
```

Notebooky treba spúšťať v tomto poradí, lebo každý používa výstupy predchádzajúceho. Pri spustení sa prekreslia aj grafy vo `figures/`, príkaz `git restore figures/` ich vráti do verzie z gitu.

## Aplikácia

Aplikácia hodnotí jednotlivé incidenty modelom VCDB z `data/processed/model_dopad_vcdb.joblib`. Pred spustením musia existovať výstupy notebookov v `data/processed/` (stačí spustiť `priprava_dat.ipynb`, `predikcia.ipynb` a `preskriptivna_udrzba.ipynb`).

```powershell
docker compose up -d --build
```

| Služba | Adresa | Obsah |
| --- | --- | --- |
| `app` | <http://localhost:8501> | Webová aplikácia Streamlit |
| `api` | <http://localhost:8000/docs> | REST API (FastAPI) s interaktívnou dokumentáciou |

Obe služby používajú rovnaký modul `opatrenia.py` a rovnakú databázu SQLite (tabuľka `hodnotenia`) vo volume Dockeru. Príkaz `docker compose down` ich zastaví.

Bez Dockera:

```bash
streamlit run app.py
uvicorn api:app --port 8000
```

Databáza je vtedy v `data/processed/hodnotenia.db`, iné umiestnenie sa dá nastaviť premennou `HODNOTENIA_DB`.

**Záložky aplikácie**

- **Nové hodnotenie:** formulár incidentu (odvetvie, veľkosť, krajina, cielenosť, typ aktéra a útoku, podrobné hodnoty, narušená integrita a dostupnosť). Ponúka iba hodnoty, ktoré sa v dátach vyskytujú aspoň 5-krát. Výsledkom sú pravdepodobnosti dopadu, očakávaná ročná strata a odporúčané opatrenie s opatreniami CIS. Tlačidlo **Náhodný testovací incident** vyplní formulár incidentom z testovacej časti dát a ukáže jeho skutočný dopad.
- **Uložené hodnotenia:** záznamy z databázy zoradené podľa očakávanej straty, s možnosťou vymazania.
- **Prehľad:** interaktívne grafy z uložených hodnotení: počet hodnotení v čase podľa dopadu, kumulatívna očakávaná strata, odporúčané opatrenia a najčastejšie vzory útokov. Obnovujú sa každých 5 sekúnd, takže zahŕňajú aj hodnotenia z API.
- **Živé sledovanie:** incidenty, ktoré posiela generátor `simulacia.py` cez API, zobrazené naživo (obnova každé 2 s): stav generátora, ukazovatele, tabuľka posledných incidentov a grafy. Popis je nižšie v časti Simulácia sledovania siete.
- **Register rizík:** 48 scenárov z notebooku, interaktívna mapa rizík, krivka rozpočtu s posuvníkom ročného rozpočtu a porovnanie stratégií. Grafy sa počítajú z dát rovnako ako grafy 7 až 9 v notebooku.
- **Predpoklady:** straty, ceny a účinnosť opatrení a prahy, od ktorých sa opatrenie oplatí.

**Simulácia sledovania siete**

Generátor [simulacia.py](simulacia.py) každých ~3 sekundy pošle náhodný testovací incident z VCDB na `POST /api/hodnotenie` so zdrojom `simulácia` a skutočným dopadom z dát. API ho vyhodnotí a uloží a záložka **Živé sledovanie** ho hneď zobrazí. API musí bežať.

```powershell
python simulacia.py                          # kým ho nezastavíte (Ctrl+C)
python simulacia.py --interval 1 --pocet 50  # 50 incidentov, jeden za sekundu
python simulacia.py --seed 67                # opakovateľné poradie incidentov
```

V Dockeri sa generátor spustí spolu s ostatnými službami príkazom `docker compose --profile simulacia up -d --build`.

**REST API**

| Metóda | Cesta | Popis |
| --- | --- | --- |
| GET | `/api/moznosti` | povolené hodnoty polí incidentu |
| POST | `/api/hodnotenie` | vyhodnotí incident a uloží výsledok do databázy (nepovinné polia `zdroj` a `skutocny_dopad` používa simulácia) |
| GET | `/api/hodnotenia` | uložené hodnotenia zoradené podľa očakávanej straty |
| GET | `/api/register` | register rizík z preskriptívnej analýzy |

Príklad z PowerShellu (dá sa vyskúšať aj priamo na <http://localhost:8000/docs> cez *Try it out*):

```powershell
$telo = @{ odvetvie = "Informácie"; aktor_typy = @("external"); akcia_typy = @("hacking"); akcia_vektory = @("hacking:Web application") } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/api/hodnotenie -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($telo))
```

Príkaz `python opatrenia.py` overí, že vstup z formulára dáva pre testovacie incidenty rovnaké pravdepodobnosti ako predikcia nad pôvodným riadkom z `vcdb_clean.csv`.
