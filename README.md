# HronTech Strojárne

Inventár firmy, bezpečnostné zistenia, simulácia incidentov a odporúčanie opatrení.

**[Webová aplikácia](https://safetyfirst-hrontech-54c15147.azurewebsites.net/)** · [API](https://safetyfirst-hrontech-54c15147.azurewebsites.net/docs) · [Stav nasadenia](https://github.com/ferkopierko/predictionandprescription/actions/workflows/deploy-hrontech.yml)

## Spustenie na PC

```powershell
pip install -r requirements.txt
python -m streamlit run hrontech/ui/app.py
```

Samostatné API: `uvicorn hrontech.api:app --port 8000`.

Ak chýbajú dáta alebo model:

```powershell
pip install -r analysis/requirements.txt
python deploy/azure/prepare_data.py
```

## Priečinky

| Priečinok | Obsah |
| --- | --- |
| `hrontech/` | Firemná logika, model a API |
| `hrontech/ui/` | Rozhranie, štýly a písma |
| `analysis/` | Notebooky a grafy |
| `docs/` | Dokumentácia a metodika |
| `deploy/` | Azure, Docker a kontroly nasadenia |
| `scripts/` | Generátor incidentov |
| `tests/` | Testy firmy a rozhrania |
| `data/` | Lokálne dáta a databáza; mimo Gitu |

## Aktualizácia webu

Push do `main` spustí testy, vytvorí balík a nasadí ho na Azure. Stav je na karte **Actions**. Aktualizácia trvá niekoľko minút; pri zmene tréningových notebookov sa vytvorí nový model. Databáza sa pri nasadení neprepisuje.

Podrobnosti: [nasadenie](deploy/azure/README.md), [dokumentácia](docs/DOKUMENTACIA.md), [vysvetlenie výpočtov](docs/VYSVETLENIE.md).

Docker: `docker compose -f deploy/docker/compose.yaml up -d --build`.

Generátor: `python -m scripts.simulacia --pocet 10 --interval 3 --seed 67`.

## Dáta

Model vychádza z [VERIS Community Database](https://github.com/vz-risk/VCDB), verzia `5ebf2f5` z 10. 11. 2026, licencia [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), Verizon RISK Team a prispievatelia VCDB. Sťahovanie overuje SHA-256. HronTech a firemné zistenia sú ukážkové údaje.
