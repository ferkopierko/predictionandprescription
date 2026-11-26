"""Prenesie konzistentnú lokálnu snímku do prázdnej databázy HronTech."""

import sqlite3
from pathlib import Path

from provision_sql import admin_connection

SNAPSHOT = Path(__file__).resolve().parents[2] / "data/processed/local-demo-snapshot.db"
TABLES = ["company_profile", "company_assets", "company_findings", "hodnotenia",
          "company_cases", "company_assessments", "company_events"]
IDENTITIES = {"hodnotenia", "company_cases", "company_events"}

with sqlite3.connect(SNAPSHOT) as source, admin_connection() as target:
    for table in TABLES:
        if target.execute(f"SELECT COUNT(*) FROM dbo.[{table}]").fetchone()[0]:
            raise RuntimeError(f"Cielova tabulka {table} uz obsahuje data. Migracia sa nevykonala.")
    for table in TABLES:
        query = ("SELECT h.* FROM hodnotenia h JOIN company_assessments c ON c.assessment_id=h.id"
                 if table == "hodnotenia" else f"SELECT * FROM {table}")
        cursor = source.execute(query)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        if rows:
            if table in IDENTITIES:
                target.execute(f"SET IDENTITY_INSERT dbo.[{table}] ON")
            sql = f"INSERT INTO dbo.[{table}] ({','.join('['+c+']' for c in columns)}) VALUES ({','.join('?' for _ in columns)})"
            target.cursor().executemany(sql, rows)
            if table in IDENTITIES:
                target.execute(f"SET IDENTITY_INSERT dbo.[{table}] OFF")
        assert target.execute(f"SELECT COUNT(*) FROM dbo.[{table}]").fetchone()[0] == len(rows)
        print(table, len(rows), flush=True)
print("Lokalny stav HronTech bol preneseny. Povodna webova databaza zostala nedotknuta.")
