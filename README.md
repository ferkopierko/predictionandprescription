# Threat Modeling and Risk Assessment

## Dataset

**CVE and CWE Mapping Dataset (2021)**, súbor `Global_Dataset.csv`, 169 566 záznamov, 56 MB.

- Odkaz: <https://huggingface.co/datasets/zefang-liu/cve-and-cwe-mapping-dataset>
- Pôvodný zdroj: <https://www.kaggle.com/datasets/krooz0/cve-and-cwe-mapping-dataset>
- Licencia: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), autor Kirushikesh DB

Samotné dáta nie sú v repozitári. `main.py` ich stiahne do `data/raw/` a overí ich kontrolný súčet.

| Stĺpec | Význam |
| --- | --- |
| `ID` | poradové číslo riadku |
| `CVE-ID` | identifikátor zraniteľnosti |
| `CVSS-V3` | skóre závažnosti CVSS v3 |
| `CVSS-V2` | skóre závažnosti CVSS v2 |
| `SEVERITY` | kategória závažnosti |
| `DESCRIPTION` | textový popis zraniteľnosti |
| `CWE-ID` | typ slabiny podľa CWE |

## Príprava dát

Kód aj dokumentácia čistenia, analýzy a vizualizácií sú v notebooku [priprava_dat.ipynb](priprava_dat.ipynb). Grafy sú v priečinku [figures/](figures/).

## Predikčná analýza

Implementácia a porovnanie logistickej regresie a LightGBM sú v notebooku [predikcia.ipynb](predikcia.ipynb). Modely odhadujú závažnosť zraniteľnosti z jej popisu a typu CWE.

Notebook [predikcia_70_30.ipynb](predikcia_70_30.ipynb) rieši zjednodušenú úlohu so zlúčenými triedami `LOW` a `MEDIUM` a náhodným rozdelením dát 70:30 so seedom 67.

## Preskriptívna údržba

Notebook [preskriptivna_udrzba.ipynb](preskriptivna_udrzba.ipynb) z predikcie závažnosti odvodzuje jedno zo 4 opatrení: monitorovanie, plánovanú opravu, dočasnú ochranu s prioritnou opravou alebo núdzovú opravu. Rozhodnutie zohľadňuje riziko, náklady, čas a prioritu. Náklady a pravdepodobnosti zneužitia sú predpoklady uvedené v notebooku, lebo dataset ich neobsahuje.

## Spustenie

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace priprava_dat.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia_70_30.ipynb
jupyter nbconvert --to notebook --execute --inplace preskriptivna_udrzba.ipynb
```

Vyčistené dáta sa uložia do `data/processed/cve_clean.csv`. Ostatné notebooky ich používajú, preto musí `priprava_dat.ipynb` bežať ako prvý.

## Aplikácia

```powershell
docker compose up -d --build
```

Príkaz `docker compose down` aplikáciu zastaví. Priečinok `data/` je do kontajnera pripojený zvonka, preto v ňom musia byť výstupy notebookov `priprava_dat.ipynb` a `preskriptivna_udrzba.ipynb`.

Bez Dockera sa aplikácia spustí príkazom `streamlit run app.py`.

Aplikácia beží na <http://localhost:8501>. Umožňuje pridať zraniteľnosť, zobraziť jej predikovanú závažnosť a odporúčané opatrenie a prezerať výsledky z notebooku. Pri prvom spustení sa model naučí a uloží do `data/processed/`, čo trvá približne 1 až 3 minúty. Pridané záznamy sa ukladajú do `data/processed/pridane_zaznamy.csv`.
