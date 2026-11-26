# safetyfirst / HronTech – samostatné demo na Azure

Web: https://safetyfirst-hrontech-54c15147.azurewebsites.net/

REST API: https://safetyfirst-hrontech-54c15147.azurewebsites.net/docs

Táto verzia je snímkou pracovnej kópie, ktorá 26. 11. 2026 bežala na `http://localhost:8501/`. Obsahuje rozhranie safetyfirst, firmu HronTech, inventár, modelové zistenia, simuláciu a hodnotenia. Nie je to staršia verzia nasadená na papu-rizika-54c15147.azurewebsites.net. Pôvodná pracovná kópia ani prvý web sa nemenili.

## Prostriedky a dáta

- Resource group: `papu-azure`, región `polandcentral`.
- App Service: `safetyfirst-hrontech-54c15147`, Python 3.13.
- Existujúci plán `papu-free-plan`, F1 / Free; vlastná webová aplikácia a identita.
- Existujúci logický SQL server `papu-sql-54c15147`, nová samostatná databáza **`papu-hrontech`**.
- Databáza má `useFreeLimit=true` a `freeLimitExhaustionBehavior=AutoPause`. Platené prekročenie limitu nie je zapnuté.
- Identita novej aplikácie má oprávnenia SELECT, INSERT, UPDATE a DELETE iba na siedmich tabuľkách novej databázy. Nepoužíva heslo.

Do novej databázy sa preniesla konzistentná SQLite snímka lokálneho firemného prostredia: profil firmy, 15 aktív, 14 zistení, 3 incidenty, 3 firemné hodnotenia s väzbami a 7 udalostí. Tri staršie všeobecné hodnotenia mimo firmy sa neprenášali, pretože ich lokálne firemné rozhranie nezobrazuje. Dáta a model VCDB sú rovnaké ako v lokálnej pracovnej kópii. Samotná SQLite snímka sa nenahráva do webového balíka a je ignorovaná Gitom.

Používatelia kolegovia pracujú so spoločnými dátami tohto dema. Zmeny a hodnotenia vidia aj ostatní návštevníci. Web aj API sú verejné bez prihlasovania. Obsah HronTech je fiktívny a simulácia neútočí na skutočnú sieť.

F1 má 60 CPU minút denne a uspávanie po nečinnosti. Nejde o limit jednej hodiny otvorenej stránky. Databáza sa uspí po 60 minútach nečinnosti a po vyčerpaní mesačného bezplatného limitu do ďalšieho mesiaca. Prvé otvorenie môže byť pomalšie. Toto nastavenie nemení ani neobmedzuje náklady ostatných služieb v predplatnom.

## Nasadenie

Hlavný spôsob aktualizácie je push do `main`. Workflow `.github/workflows/deploy-hrontech.yml` vytvorí balík, spustí testy a nasadí ho na tento web. Dá sa spustiť aj ručne cez GitHub → Actions → Deploy HronTech to Azure → Run workflow.

GitHub sa prihlasuje cez OIDC a user-assigned identitu `hrontech-github-deploy`. Dôvera platí len pre `repo:ferkopierko/predictionandprescription:ref:refs/heads/main`. Identita má rolu Website Contributor iba na HronTech App Service. Nevyžaduje heslo, publish-profile secret ani oprávnenia k SQL databáze.

Čistý runner vytvorí dáta a model z pripnutého VCDB zdroja; päť výstupov sa následne ukladá do cache viazanej na obsah notebookov, prípravných modulov a závislostí. Lokálna SQLite databáza sa do balíka nedostane. Nasadenie nevykonáva migráciu ani reinicializáciu používateľských dát. Endpoint `/health` obsahuje Git revision nasadeného balíka; workflow overí, že web už obsluhuje práve nasadený commit, aj funkčnosť firemného API.

Stav: https://github.com/ferkopierko/predictionandprescription/actions/workflows/deploy-hrontech.yml

Pôvodná verzia `579ccb7`, história, rozpracovaná pracovná kópia a konzistentná lokálna databáza boli pred nahradením zálohované na PC do `C:\Users\samoo\Documents\PaPU\zalohy\pred-hrontech-2026-11-26-210802`.

`azure_app.py` spojí pôvodné REST API a Streamlit cez `st.App` do jedného procesu. `startup.sh` spúšťa jeden Uvicorn worker na porte 8000; viac workerov by rozdeľovalo Streamlit relácie v pamäti. Úpravy v `opatrenia.py` a `firma.py` pridávajú podporu Azure SQL pri zachovaní lokálneho SQLite režimu.

Z koreňa tejto pracovnej kópie s pripravenými piatimi súbormi `data/processed/`:

```powershell
python deploy/azure/package.py
az webapp config appsettings set -g papu-azure -n safetyfirst-hrontech-54c15147 --settings '@deploy/azure/appsettings.json' -o none
az webapp deploy -g papu-azure -n safetyfirst-hrontech-54c15147 --src-path ../hrontech-azure.zip --type zip --timeout 1200000 --async true --track-status false
```

`schema.sql` a `provision_sql.py` pripravia iba novú databázu a prístup novej identity. `migrate_snapshot.py` odmietne import, ak cieľové tabuľky obsahujú dáta. Tieto skripty sú na počiatočné nasadenie, nie na opakované nahrávanie používateľských dát. Firewall povoľuje konkrétne možné odchádzajúce IP adresy webu; pri zmene plánu treba zoznam skontrolovať.

Balík obsahuje iba potrebný Python kód, produkčné závislosti, vzhľad, obrázky a výstupy VCDB. Neobsahuje `.venv`, Git, notebooky ani lokálne databázy.

## Overenie

- `python -m unittest discover -s tests -v`: 13 pôvodných testov firmy.
- `python deploy/azure/verify_local.py`: SQLite, spoločný ASGI server, všetky firemné API a hodnotenie. Testovací klient vyžaduje `pip install httpx2`.
- `verify_company_sql.py`: skutočný SQL zápis aktíva a zistenia, zmena stavu, simulácia, vyhodnotenie, úprava nastavení, kaskádové vymazanie; testovacie zmeny sa upracú. Vyžaduje administračný prístup a je určený na kontrolu pred sprístupnením dema.
- Streamlit AppTest: všetkých osem stránok bez výnimiek.
- `python deploy/azure/verify_remote.py`: verejné HTTP API a vykreslenie všetkých ôsmich stránok cez WebSocket.

Generátor možno spustiť aj lokálne proti novému webu:

```powershell
python simulacia.py --api https://safetyfirst-hrontech-54c15147.azurewebsites.net --pocet 10 --interval 3 --seed 67
```

Trvalý generátor nie je automaticky spustený; jednotlivé situácie sa dajú vytvárať priamo na stránke Simulácia.
