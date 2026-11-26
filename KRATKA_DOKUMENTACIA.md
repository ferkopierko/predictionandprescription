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

IS safetyfirst je prispôsobený simulovanej výrobnej firme **HronTech Strojárne, s. r. o.** (82 zamestnancov, Banská Bystrica). Obsahuje 15 skupín aktív a 14 počiatočných modelových zraniteľností. Údaje firmy sú fiktívne; historický tréningový dataset VCDB zostáva reálny.

- **Firma:** inventár, weby, zraniteľnosti a nastavenie ekonomických predpokladov.
- **Simulácia:** sedem rodín incidentov, väzba na otvorené zistenie a konkrétne aktívum.
- **Nové hodnotenie:** firemné aktívum → okolnosti incidentu → model dopadu a výber ochrany.
- **Uložené hodnotenia a Prehľad:** história iba tejto firmy.
- **Živé sledovanie:** automaticky obnovované hodnotenia od generátora alebo všetky firemné záznamy.
- **Register rizík:** firemné scenáre a poradie opatrení v rozpočte.
- **Predpoklady:** vysvetlenie modelu a nastavených cien, účinnosti a strát.

Frontend a REST API používajú `firma.py`, ktorý zdieľa model z `opatrenia.py`. SQLite obsahuje inventár, zraniteľnosti, incidenty, hodnotenia, ich väzby, ekonomické predpoklady a denník zmien. Z výsledku sa dá otvoriť súvisiaca zraniteľnosť a zapísať stav jej riešenia.

Predvolené firemné predpoklady sú 45 000 € ročný rozpočet, straty 5 000 / 50 000 / 500 000 € podľa tried dopadu, ceny ochrany na úrovni 35 % základného modelu a trojročný horizont. Dajú sa meniť. Výsledky notebookov vyššie sú základný experiment a používajú iné finančné predpoklady.

## Simulácia sledovania

`simulacia.py` pravidelne vytvorí firemný incident cez `/api/firma/simulacia` a vyhodnotí ho cez `/api/hodnotenie`. Posiela povinné ID aktíva, zraniteľnosti a incidentu, nastavenú frekvenciu a zdroj `simulácia`. Všetky udalosti patria HronTech. Skutočný dopad pri týchto scenároch nepoznáme, preto sa nevykazuje vymyslená úspešnosť predikcie.

```text
Generátor → firemný incident → API → model + firemné predpoklady → SQLite → živé sledovanie
```

Generátor nemonitoruje ani nenapáda reálnu sieť. Živé sledovanie sa obnovuje každé dve sekundy. Model odhaduje rozsah úniku dát; nepredikuje fyzickú poruchu CNC, dobu odstávky ani pravdepodobnosť zneužitia zraniteľnosti.

## Spustenie

Príprava prostredia a notebookov je opísaná v README. Po vygenerovaní dát a modelu:

```powershell
streamlit run app.py
uvicorn api:app --host 127.0.0.1 --port 8000
python simulacia.py --pocet 10 --interval 3 --seed 67
```

S Dockerom: `docker compose --profile simulacia up -d --build`. Bez profilu sa spustí iba web a API. Adresy sú <http://localhost:8501> a <http://localhost:8000/docs>. Dáta SQLite sa zachovajú po reštarte.

## Overenie a obmedzenia

`python -m unittest discover -s tests -v` testuje integritu firemných väzieb, ekonomiku, uložené predpoklady, históriu, opravy aj kompatibilitu generátora a API. `python opatrenia.py` porovná prípravu znakov s notebookom.

Ceny, frekvencie a účinnosť opatrení sú modelové predpoklady. Počty zariadení sú evidencia a samy nemenia predikciu. Jednorazový odhad opravy je oddelený od ročných cien CIS. Stav „Odstránená“ nie je technické overenie opravy. Spoločné opatrenia medzi scenármi sa cenovo nezlučujú a opakované udalosti sa nesmú sčítať ako nezávislé ročné riziká celej firmy.
