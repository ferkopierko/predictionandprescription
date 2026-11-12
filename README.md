# Threat Modeling and Risk Assessment

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

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace priprava_dat.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia.ipynb
jupyter nbconvert --to notebook --execute --inplace predikcia_70_30.ipynb
jupyter nbconvert --to notebook --execute --inplace preskriptivna_udrzba.ipynb
```

Notebooky treba spúšťať v tomto poradí, lebo každý používa výstupy predchádzajúceho.

## Aplikácia

```powershell
docker compose up -d --build
```

Aplikácia beží na <http://localhost:8501> a príkaz `docker compose down` ju zastaví. Bez Dockera sa spustí príkazom `streamlit run app.py`.

Aplikácia zatiaľ používa **pôvodný model nad datasetom CVE** z predchádzajúcej verzie projektu a potrebuje jeho dáta v `data/processed/cve_clean.csv`. Na model VCDB ešte nie je prepojená.
