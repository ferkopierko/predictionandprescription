# Ako to celé funguje

Tento dokument vysvetľuje projekt krok za krokom a jednoduchými slovami: čo sa deje s dátami, ako sa model učí, ako sa z predikcie stane odporúčanie a prečo je každé rozhodnutie urobené práve takto. Presné čísla a tabuľky výsledkov sú v [DOKUMENTACIA.md](DOKUMENTACIA.md).

## Obsah

1. [Celý proces na jednom mieste](#1-celý-proces-na-jednom-mieste)
2. [Krok 1: odkiaľ sú dáta](#2-krok-1-odkiaľ-sú-dáta)
3. [Krok 2: čistenie a úprava dát](#3-krok-2-čistenie-a-úprava-dát)
4. [Krok 3: ako sa model učí predikovať dopad](#4-krok-3-ako-sa-model-učí-predikovať-dopad)
5. [Krok 4: ako sa z predikcie stane odporúčanie](#5-krok-4-ako-sa-z-predikcie-stane-odporúčanie)
6. [Riešený príklad](#6-riešený-príklad)
7. [Ako súbory spolu súvisia](#7-ako-súbory-spolu-súvisia)
8. [Slovník pojmov](#8-slovník-pojmov)
9. [Časté otázky pri obhajobe](#9-časté-otázky-pri-obhajobe)

---

## 1. Celý proces na jednom mieste

```
 VCDB (10 047 incidentov, JSON)
        │  vcdb_data.py: stiahne a overí kontrolný súčet
        ▼
 priprava_dat.ipynb
   čistenie → tabuľka 9 961 × 50 → vzor útoku, trieda dopadu → analýza, 2 grafy
        │  vcdb_clean.csv, vcdb_opatrenia_cis.csv
        ▼
 predikcia.ipynb
   logistická regresia vs. LightGBM → metriky → kalibrácia → vyberie LightGBM
        │  vcdb_predikcie.csv (pravdepodobnosti), model_dopad_vcdb.joblib
        ▼
 preskriptivna_udrzba.ipynb
   48 scenárov → riziko × náklady × čas → najlacnejšie opatrenie → priorita
        │  vcdb_register_rizik.csv, grafy 7 až 9
        ▼
 Odporúčanie: ktoré opatrenie, pri ktorej hrozbe a v akom poradí
```

Jednou vetou: **zistíme, aké incidenty sa stávajú, naučíme model odhadnúť, aký veľký bude ich dopad, a potom pre každú hrozbu vyberieme opatrenie, ktoré organizáciu bude stáť celkovo najmenej.**

## 2. Krok 1: odkiaľ sú dáta

**VCDB** (VERIS Community Database) je verejná databáza bezpečnostných incidentov, ktorú vedie Verizon. Každý incident je jeden záznam v JSON a opisuje 4 veci (model **4A**):

| Časť | Otázka | Príklad |
| --- | --- | --- |
| Actor | Kto útočil? | externý hacker, zamestnanec, partner |
| Action | Ako? | hacking, malvér, phishing, chyba, krádež |
| Asset | Na čo? | server, notebook, papierové dokumenty |
| Attribute | Čo sa narušilo? | dôvernosť (únik), integrita, dostupnosť |

Navyše vieme, v akom odvetví a akej veľkej firme sa to stalo a pri úniku dát aj **koľko záznamov uniklo**. To je kľúčové, lebo z toho vieme určiť dopad.

[vcdb_data.py](vcdb_data.py) stiahne presne jednu verziu (pripnutý commit) a overí jej SHA-256. Vďaka tomu dostane každý, kto projekt spustí, rovnaké dáta a rovnaké výsledky.

## 3. Krok 2: čistenie a úprava dát

Notebook [priprava_dat.ipynb](priprava_dat.ipynb). Najprv sa zisťuje, aké problémy dáta majú, a až potom sa čistia:

1. **Duplikáty.** Identifikátor `incident_id` sa opakuje, ale väčšinou ide o rôzne incidenty. Preto sa mažú iba úplne rovnaké záznamy (2).
2. **Nepotvrdené incidenty.** „Podozrenie“ alebo „takmer incident“ nie je incident, preto sa vyhodí (81).
3. **Neplatné záznamy** so stavom `Ineligible` (3).
4. **Rozbalenie JSON do tabuľky.** Model nevie pracovať s vnoreným JSON, potrebuje riadky a stĺpce. Z každého incidentu vznikne jeden riadok. Napríklad pre každý typ aktéra vznikne stĺpec áno/nie.
5. **`Unknown` sa ponechá.** Vo VERIS to znamená „nevieme“ a aj to je informácia, preto sa nedopĺňa vymyslenou hodnotou.

Potom sa doplnia nové stĺpce:

- **Trieda dopadu** podľa počtu uniknutých záznamov: do 999 `nízky`, do 99 999 `stredný`, od 100 000 `vysoký`. Hranice sú rády veľkosti.
- **Vzor útoku**: celý incident sa zhrnie do jedného z 8 scenárov (chyby, krádež, prienik do systému…). Pravidlá sa skúšajú v poradí a platí prvé, ktoré sedí.
- **Reprezentatívny incident**: náhodne vybraný a nie z hromadného zoznamu. Prečo? VCDB niektoré incidenty pridáva cielene (napríklad zo zdravotníctva) a niektoré články pridali naraz stovky incidentov. Keby sme z nich počítali, ako často sa niečo stáva, výsledok by bol skreslený.

**Výsledok:** 9 961 incidentov. Z nich 6 270 sa použije na odhad pravdepodobnosti a 5 097 so známym dopadom na učenie modelu.

**Dve vizualizácie:**
- *Matica rizika* ukazuje, že najčastejšie sú chyby, ale najväčší dopad majú webové útoky a prieniky do systému. Častosť a závažnosť sú teda dve rôzne veci.
- *Vzory podľa odvetvia* ukazuje, že každé odvetvie má iný hlavný problém (zdravotníctvo krádež zariadení, IT firmy webové útoky, obchody skimmery).

## 4. Krok 3: ako sa model učí predikovať dopad

Notebook [predikcia.ipynb](predikcia.ipynb).

### Otázka, na ktorú model odpovedá

> Práve sme odhalili incident. Vieme, kto útočil, ako, na čo a v akej firme. Bude mať nízky, stredný alebo vysoký dopad?

### Čo model dostane na vstup a čo nie

Vstupom sú iba veci, ktoré vieme **hneď po odhalení**: aktér, spôsob útoku, aktívum, typ dát, odvetvie, veľkosť firmy, krajina. Spolu 232 číselných znakov.

Zámerne **nie je** vstupom textový popis incidentu, lebo v ňom často priamo stojí „unikli údaje 2 miliónov zákazníkov“. Model by tak „podvádzal“, v teste by vyzeral skvele, ale v praxi by nefungoval. Tomu sa hovorí **únik informácií** (*data leakage*).

### Ako sa dáta rozdelia na učenie a test

Model sa učí na jednej časti dát a skúša na inej, ktorú nikdy nevidel. Tu je dôležitá jedna vec: veľa incidentov pochádza z toho istého článku a sú si takmer rovnaké. Keby boli zároveň v tréningu aj v teste, model by si ich len zapamätal. Preto:

- všetky incidenty z jedného zdroja sú vždy spolu v tej istej časti (`StratifiedGroupKFold`),
- veľké hromadné zoznamy sú iba v tréningu,
- test (1 052 incidentov) sa použije **iba raz na konci**.

Pri prvom pokuse padol do testu zoznam 687 takmer rovnakých incidentov a model vyzeral lepšie, než v skutočnosti bol (F1 0,80). Preto vzniklo toto pravidlo.

### Dva algoritmy

**Logistická regresia** dá každému znaku váhu. Napríklad „stratená zálohovacia páska“ zvyšuje skóre triedy `vysoký`, „omylom doručený list“ zvyšuje skóre triedy `nízky`. Skóre sa sčítajú a prevedú na pravdepodobnosti. Je jednoduchá a dá sa ľahko vysvetliť.

**LightGBM** stavia veľa malých rozhodovacích stromov za sebou. Prvý strom urobí hrubý odhad, druhý sa učí opraviť jeho chyby, tretí chyby druhého atď. Vďaka tomu zachytí aj kombinácie, napríklad „hacking cez web **a zároveň** osobné údaje“.

Oba majú nastavené `class_weight="balanced"`: incidentov s vysokým dopadom je málo, a bez tohto nastavenia by ich model radšej ignoroval.

### Výber parametrov

Pre každý algoritmus sa vyskúša niekoľko nastavení (napríklad počet stromov) a vyberie sa to, ktoré má najlepšie **macro F1** v 5-násobnej krížovej validácii: tréningové dáta sa rozdelia na 5 častí, 4 sa použijú na učenie a 1 na overenie, a to sa zopakuje 5-krát.

### Kalibrácia: prečo je dôležitá

Model povie napríklad „vysoký dopad s pravdepodobnosťou 60 %“. Kvôli vyváženiu tried sú však tieto čísla posunuté v prospech zriedkavých tried. Na triedenie to nevadí, ale preskripcia z pravdepodobností počíta peniaze, takže musia byť pravdivé. Preto sa nad modelom naučí ešte malý **kalibrátor**, ktorý pravdepodobnosti opraví tak, aby „60 %“ naozaj znamenalo, že sa to stane asi v 6 z 10 prípadov.

### Výsledok

| | Logistická regresia | LightGBM |
| --- | ---: | ---: |
| Macro F1 | 0,656 | 0,660 |
| Zachytí vysoký dopad (recall) | 79 % | 77 % |
| Kvalita pravdepodobností (log loss, menej je lepšie) | 0,759 | 0,735 |

Oba modely sú v triedení prakticky rovnako dobré, rozdiel je v rámci náhody. LightGBM má však **spoľahlivo lepšie pravdepodobnosti**, a tie preskripcia potrebuje. Preto je vybraný LightGBM. Pre porovnanie, triviálny model, ktorý vždy tipne najčastejšiu triedu, má macro F1 iba 0,19.

## 5. Krok 4: ako sa z predikcie stane odporúčanie

Notebook [preskriptivna_udrzba.ipynb](preskriptivna_udrzba.ipynb).

### Scenáre

Scenár = **odvetvie × vzor útoku**, napríklad „zdravotníctvo – krádež zariadení“. 6 odvetví × 8 vzorov = **48 scenárov**.

### Riziko scenára

```
riziko (očakávaná ročná strata) = ako často × aký veľký dopad
```

- **Ako často:** organizácia má v priemere 1 závažný incident ročne. Ak v zdravotníctve tvorí krádež zariadení 43 % incidentov, frekvencia scenára je 0,43 za rok.
- **Aký veľký dopad:** model povie pravdepodobnosti tried, napríklad 50 % nízky, 30 % stredný, 20 % vysoký. Každá trieda má cenu (25 tis., 250 tis., 2,5 mil. €), takže očakávaná strata jedného incidentu je `0,5 × 25 000 + 0,3 × 250 000 + 0,2 × 2 500 000`.

### Štyri možnosti, čo s rizikom urobiť

| Opatrenie | Čo robí | Analógia z údržby |
| --- | --- | --- |
| Akceptovať a monitorovať | nič, len sledujeme | stroj necháme bežať |
| Prevencia | menej incidentov (−40 %) | preventívna výmena súčiastok |
| Detekcia a reakcia | menšia škoda z incidentu (−35 %) | senzory a rýchly servis |
| Komplexná ochrana | oboje | oboje |

Každá možnosť má **cenu** (súčet cien konkrétnych opatrení CIS Controls) a **čas zavedenia**. Opatrenie, ktoré sa zavádza 4 mesiace, chráni v trojročnom horizonte iba 32 z 36 mesiacov.

### Pravidlo výberu

Pre každú možnosť sa spočíta:

```
celkové náklady = cena opatrenia + strata, ktorá aj tak zostane
```

a vyberie sa tá **s najnižším súčtom**. Lacné opatrenie pri veľkom riziku nechá veľkú stratu, drahé opatrenie pri malom riziku sa nevráti. Pravidlo samo nájde rovnováhu.

### Priorita

Ak firma nemá peniaze na všetko (všetky odporúčania stoja 702 tis. € ročne), scenáre sa zoradia podľa toho, **koľko eur straty ušetrí každé investované euro**, a zavádzajú sa od najvýhodnejšieho.

### Ako vieme, že to funguje

Rôzne stratégie sa porovnajú na skutočnom dopade testovacích incidentov:

- **Naše riešenie:** 589 913 € ročne na organizáciu.
- **Teoretické optimum** (keby sme dopad poznali dopredu): 588 393 €. Sme len o 1 520 € horší.
- **Najlepšia jednoduchá stratégia** (všade detekcia a reakcia): 717 111 €. Ušetríme 17,7 %.
- Aj keď sa zmenia predpoklady (ceny 2×, straty 0,5× a pod.), riešenie vždy vyhrá nad jednoduchými stratégiami.

## 6. Riešený príklad

**Scenár: odvetvie informácií, útok na webovú aplikáciu.**

1. **Frekvencia.** Webové útoky tvoria v tomto odvetví 34,3 % incidentov → 0,343 incidentu ročne.
2. **Dopad.** Model pre takéto incidenty predikuje vysoký dopad s pravdepodobnosťou 61 %. Očakávaná strata jedného incidentu vychádza približne 1,6 mil. €.
3. **Riziko.** 0,343 × 1,6 mil. € ≈ **548 250 € ročne**.
4. **Opatrenia** (opatrenia CIS pre webové útoky: CIS 6, 7, 16 prevencia a CIS 17 reakcia):

| Opatrenie | Cena | Funguje časť horizontu | Zostane zo straty | Zostávajúca strata | **Spolu** |
| --- | ---: | ---: | ---: | ---: | ---: |
| Akceptovať | 2 000 € | 100 % | 100 % | 548 250 € | 550 250 € |
| Prevencia | 45 000 € | 33/36 | 63,3 % | 347 225 € | 392 225 € |
| Detekcia a reakcia | 15 000 € | 34/36 | 66,9 % | 367 023 € | 382 023 € |
| **Komplexná ochrana** | 60 000 € | 32/36 | 44,4 % | 243 396 € | **303 396 €** |

5. **Rozhodnutie:** komplexná ochrana, lebo má najnižšie celkové náklady. Oproti nečinnosti ušetrí 246 854 € ročne.

Výpočet „zostane zo straty“ pri komplexnej ochrane: `(1 − 0,40 × 32/36) × (1 − 0,35 × 32/36) = 0,644 × 0,689 = 0,444`.

Pre porovnanie, pri zdravotníctve a krádeži zariadení je riziko 112 tis. €, ale dopad je väčšinou malý (vysoký iba 4 %). Tam vyjde najlepšie lacná detekcia a reakcia.

## 7. Ako súbory spolu súvisia

| Súbor | Úloha | Číta | Zapisuje |
| --- | --- | --- | --- |
| [vcdb_data.py](vcdb_data.py) | stiahne a overí VCDB | internet | `data/raw/vcdb/vcdb.json.zip` |
| [priprava_dat.ipynb](priprava_dat.ipynb) | čistenie, analýza, grafy 1 a 2 | VCDB | `vcdb_clean.csv`, `vcdb_opatrenia_cis.csv` |
| [vcdb_model.py](vcdb_model.py) | príprava znakov pre model | – | – |
| [predikcia.ipynb](predikcia.ipynb) | 2 modely, metriky, grafy 3 a 4 | `vcdb_clean.csv` | `vcdb_predikcie.csv`, `model_dopad_vcdb.joblib` |
| [predikcia_70_30.ipynb](predikcia_70_30.ipynb) | jednoduchšia úloha, grafy 5 a 6 | `vcdb_clean.csv` | – |
| [preskriptivna_udrzba.ipynb](preskriptivna_udrzba.ipynb) | odporúčania, grafy 7 až 9 | všetky 3 CSV vyššie | `vcdb_register_rizik.csv` |
| [app.py](app.py), [api.py](api.py), [opatrenia.py](opatrenia.py) | webová aplikácia a REST API | `model_dopad_vcdb.joblib`, všetky 3 CSV vyššie | SQLite databáza `hodnotenia` |

Funkcie na prípravu znakov sú v samostatnom súbore [vcdb_model.py](vcdb_model.py), aby sa uložený model dal načítať aj mimo notebooku, napríklad v aplikácii.

## 8. Slovník pojmov

| Pojem | Vysvetlenie |
| --- | --- |
| **Accuracy** | Podiel správnych odpovedí. Pri nevyvážených triedach klame: model, ktorý vždy povie „nízky“, má 40 %. |
| **Precision** | Keď model povie „vysoký“, ako často má pravdu. |
| **Recall** | Z incidentov, ktoré naozaj mali vysoký dopad, koľko model zachytil. |
| **F1** | Spája precision a recall do jedného čísla (harmonický priemer). |
| **Macro F1** | Priemer F1 cez všetky triedy, každá trieda má rovnakú váhu, aj tá malá. |
| **MAE poradia** | O koľko tried sa model v priemere mýli (nízky → vysoký je chyba 2). |
| **Log loss** | Trestá model, keď si je istý a mýli sa. Meria kvalitu pravdepodobností. |
| **ROC AUC** | Ako dobre model zoradí incidenty od najrizikovejšieho. 0,5 je náhoda, 1 je dokonalosť. |
| **Krížová validácia** | Dáta sa rozdelia na k častí a model sa k-krát učí a overuje, vždy na inej časti. |
| **Bootstrap** | Opakovaný náhodný výber z testu s vracaním. Ukáže, či je rozdiel medzi modelmi skutočný alebo náhodný. |
| **Kalibrácia** | Úprava pravdepodobností tak, aby zodpovedali skutočnosti. |
| **Data leakage** | Model dostane na vstup informáciu, ktorú by v praxi nemal. Výsledky potom vyzerajú lepšie, než sú. |
| **One-hot** | Kategória sa zmení na stĺpce 0/1, jeden pre každú hodnotu. |
| **Očakávaná strata** | Pravdepodobnosť × výška škody, sčítaná cez všetky možné výsledky. |
| **CIS Controls v8** | Uznávaný zoznam 18 bezpečnostných opatrení, napríklad CIS 3 ochrana dát, CIS 17 reakcia na incidenty. |

## 9. Časté otázky pri obhajobe

**Prečo nie je accuracy hlavná metrika?**
Triedy sú nevyvážené. Triviálny model má accuracy 40 %, ale nezachytí ani jeden vysoký dopad. Macro F1 dáva rovnakú váhu každej triede.

**Prečo ste vybrali LightGBM, keď je v triedení rovnako dobrý ako logistická regresia?**
Lebo preskripcia počíta s pravdepodobnosťami a tie má LightGBM spoľahlivo lepšie (log loss nižší, 95 % interval rozdielu neobsahuje nulu). Výber bol urobený podľa krížovej validácie, nie podľa testu.

**Prečo delíte dáta podľa zdroja a nie náhodne?**
Incidenty z jedného článku sú takmer rovnaké. Pri náhodnom delení by model v teste „spoznal“ incidenty z tréningu a výsledok by bol prikrášlený. Náhodné delenie 70:30 je pre porovnanie v [predikcia_70_30.ipynb](predikcia_70_30.ipynb).

**Kde ste vzali ceny opatrení a straty?**
Dataset ich neobsahuje, sú to predpoklady pre modelovú organizáciu. Preto je súčasťou analýza citlivosti: aj pri polovičných alebo dvojnásobných hodnotách riešenie vždy prekonalo jednoduché stratégie. Dôležité je poradie a logika rozhodovania, nie presné sumy.

**Prečo sa pri polovici scenárov odporúča iba monitorovanie?**
Najlacnejšie opatrenie stojí 15 000 € ročne. Ak je očakávaná strata scenára nižšia ako približne 35 až 40 tisíc €, opatrenie sa nevráti.

**Aký je prínos modelu oproti histórii?**
Na úrovni celých scenárov malý (menej ako 1 %), lebo priemer predikcií sa blíži historickému priemeru. Model je užitočnejší pri jednotlivých nových incidentoch, kde vie dopad odhadnúť z konkrétnych okolností.

**Prečo VCDB a nie CVE?**
CVE opisuje chyby v softvéri, nie útoky. Nevieme z neho, kto útočil ani aký bol dopad. Na hodnotenie rizika potrebujeme pravdepodobnosť aj dopad a tie má iba databáza incidentov.

**Ako je riešenie integrované do informačného systému?**
Webová aplikácia (Streamlit) aj REST API (FastAPI) používajú uložený model VCDB a rovnaký výpočet opatrení ako notebook. Hodnotenia ukladajú do spoločnej databázy SQLite a obe bežia v Dockeri. BPMN diagram procesu bol súčasťou zadania č. 1.
