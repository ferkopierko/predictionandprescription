# safetyfirst · HronTech Strojárne

Webová aplikácia pre simulovanú výrobnú firmu HronTech: inventár aktív, modelové bezpečnostné zistenia, simulácia incidentov, predikcia dopadu a odporúčanie opatrení.

**[Otvoriť web](https://safetyfirst-hrontech-54c15147.azurewebsites.net/)** · **[REST API](https://safetyfirst-hrontech-54c15147.azurewebsites.net/docs)** · **[Stav automatického nasadenia](https://github.com/ferkopierko/predictionandprescription/actions/workflows/deploy-hrontech.yml)**

## Aktualizácia webu z Gitu

Každý push do vetvy `main` spustí GitHub Actions: prípravu dát a modelu, testy, vytvorenie balíka a nasadenie na Azure. Zmeny sa prejavia po úspešnom dokončení workflow, spravidla v priebehu niekoľkých minút. Prvý beh alebo zmena tréningových notebookov trvá dlhšie; nezmenené výstupy modelu sa používajú z cache.

Azure SQL databáza je samostatná a pri nasadení sa neprepisuje. Hodnotenia, inventár a nastavenia uložené návštevníkmi zostávajú zachované. Lokálny beh používa SQLite. Podrobnosti a manuálne nasadenie sú v [deploy/azure/README.md](deploy/azure/README.md).

Podrobný opis riešenia je v [DOKUMENTACIA.md](DOKUMENTACIA.md) a vysvetlenie, ako jednotlivé časti fungujú, v [VYSVETLENIE.md](VYSVETLENIE.md).

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

## Aplikácia safetyfirst: HronTech Strojárne

Funkčný IS je prispôsobený jednej **fiktívnej výrobnej firme HronTech Strojárne, s. r. o.** v Banskej Bystrici. Má 82 zamestnancov, 15 skupín aktív (kancelárske a CAD počítače, výrobné terminály a CNC riadenie, ERP, databázu, doménové radiče, súborový server, zálohy, VPN, web a zákaznícky portál) a 14 počiatočných modelových zraniteľností.

Firma, inventár, zraniteľnosti a incidenty sú simulované. Adresy `*.example` nie sú reálne ciele a aplikácia nič neskenuje. Predikčný model používa skutočné historické dáta VCDB. Nehodnotí CVSS ani pravdepodobnosť zneužitia zraniteľnosti; odhaduje rozsah prípadného úniku dát.

Pred spustením musia existovať výstupy notebookov v `data/processed/`. Stačí spustiť `priprava_dat.ipynb`, `predikcia.ipynb` a `preskriptivna_udrzba.ipynb`.

```powershell
docker compose up -d --build
```

| Služba | Adresa |
| --- | --- |
| Streamlit | <http://localhost:8501> |
| REST API a jeho dokumentácia | <http://localhost:8000/docs> |

Bez Dockera, v dvoch termináloch s aktivovaným prostredím:

```powershell
streamlit run app.py
uvicorn api:app --host 127.0.0.1 --port 8000
```

Databáza SQLite je v `data/processed/hodnotenia.db`; cestu mení `HODNOTENIA_DB`. Firemné tabuľky sa pri prvom spustení naplnia iba raz, zmeny potom pretrvajú reštart. Staršie všeobecné hodnotenia sa nemažú, ale v histórii firmy sa zobrazujú iba firemné záznamy.

### Použitie

1. **Firma:** inventár aktív a webov, detaily, súvisiace zraniteľnosti a ich evidencia. Možno pridávať aktíva a zistenia a meniť stav riešenia.
2. **Simulácia:** sedem pripravených scenárov. Spustenie založí incident a predvyplní konkrétne aktívum, súvisiacu zraniteľnosť a okolnosti incidentu.
3. **Nové hodnotenie:** výber firemného aktíva, údaje o incidente a frekvencia. Odvetvie výroby, veľkosť a krajina sa dopĺňajú z profilu. Výsledok obsahuje pravdepodobnosti dopadu, porovnanie opatrení, konkrétnu opravu prepojenej zraniteľnosti a informáciu, či odporúčanie pokrýva rozpočet.
4. **Uložené hodnotenia a Prehľad:** história firmy, export, filtre a grafy. Každé hodnotenie je previazané s aktívom a prípadne s incidentom a zraniteľnosťou.
5. **Register rizík:** aktuálne firemné scenáre a výber ekonomicky prínosných opatrení v rozpočte. Rodina incidentov sa počíta iba raz, nie raz za každé zistenie.
6. **Predpoklady:** vysvetlenie modelu a ekonomiky. Nastavenia sa menia cez Firma → Nastavenie firmy.

Predvolený ročný rozpočet je 45 000 €, finančné straty podľa dopadu 5 000 / 50 000 / 500 000 €, koeficient cien ochrany 0,35 a horizont tri roky. Tieto hodnoty sa reálne používajú vo výpočte a ich kópia sa ukladá k hodnoteniu. Modelové účinnosti opatrení zostávajú 40 % pre prevenciu a 35 % pre detekciu a reakciu.

Jednorazová cena opravy zraniteľnosti je oddelený evidenčný odhad, nie ročná cena balíka CIS. Zmena stavu zraniteľnosti eviduje rozhodnutie analytika; nedokazuje vykonanú technickú opravu ani automatické zníženie frekvencie. Pri plánovaní sa môžu prekrývať spoločné CIS opatrenia; ich ceny sa medzi scenármi nezlučujú. Model nepredikuje fyzické poruchy CNC ani trvanie odstávky.

### REST API

| Metóda | Cesta | Obsah |
| --- | --- | --- |
| GET | `/api/firma` | profil firmy |
| GET | `/api/firma/aktiva` | inventár |
| GET | `/api/firma/zranitelnosti` | evidencia zistení |
| PATCH | `/api/firma/zranitelnosti/{id}` | stav a poznámka k riešeniu |
| GET | `/api/firma/scenare` | pripravené scenáre |
| POST | `/api/firma/simulacia` | vytvorenie simulovaného incidentu |
| GET | `/api/firma/incidenty` | história simulácií |
| GET | `/api/moznosti` | podporované vstupné hodnoty |
| POST | `/api/hodnotenie` | hodnotenie viazané na povinné `asset_id` |
| GET | `/api/hodnotenia` | iba hodnotenia HronTech |
| GET | `/api/register` | firemné plánovacie scenáre |

Príklad vytvorenia incidentu a následného vyhodnotenia:

```powershell
$case = Invoke-RestMethod -Method Post http://localhost:8000/api/firma/simulacia -ContentType 'application/json' -Body '{"scenario":"portal"}'
$body = @{
    asset_id = $case.asset_id
    finding_id = $case.finding_id
    case_id = $case.id
    nazov = $case.title
    frekvencia = $case.frequency
}
$case.input.psobject.Properties | ForEach-Object { $body[$_.Name] = $_.Value }
$json = $body | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Post http://localhost:8000/api/hodnotenie -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json))
```

### Overenie

```powershell
python -m unittest discover -s tests -v
python opatrenia.py
```

Testy firemnej vrstvy používajú dočasnú databázu: overujú väzby, uloženie incidentov, oddelenie histórie, ekonomické predpoklady, ich uložené kópie a evidenciu opráv. `python opatrenia.py` overuje zhodu prípravy znakov s pôvodným notebookom.

### Živé sledovanie a generátor

Funkcia z merge `579ccb7` je zachovaná a prispôsobená firme. Generátor posiela sedem typov firemných scenárov s povinnými väzbami na aktívum, zraniteľnosť a incident. Používa `zdroj: "simulácia"`; nevymýšľa skutočný dopad. Pole `skutocny_dopad` zostáva voliteľnou metainformáciou API a nevstupuje do modelu.

```powershell
python simulacia.py --pocet 10 --interval 3 --seed 67
```

Stránka **Živé sledovanie** sa obnovuje každé dve sekundy a ukazuje iba firemné hodnotenia. S Dockerom zostáva dostupný profil `docker compose --profile simulacia up -d --build`. Bez profilu sa generátor automaticky nespúšťa. Pôvodný generátor náhodných záznamov z rôznych organizácií bol nahradený firemnými scenármi; payload bez `asset_id` už nie je platný. Parametre `--api`, `--interval`, `--rozptyl`, `--pocet` a `--seed` zostávajú zachované.
