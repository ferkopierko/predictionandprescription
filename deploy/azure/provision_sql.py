"""Schéma a minimálne oprávnenia iba pre samostatné demo HronTech."""

import json
import struct
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

import mssql_python

AZ = Path("C:/Program Files/Microsoft SDKs/Azure/CLI2/wbin/az.cmd")
GROUP = "papu-azure"
SERVER = "papu-sql-54c15147"
DATABASE = "papu-hrontech"
APP = "safetyfirst-hrontech-54c15147"
TABLES = ["hodnotenia", "company_profile", "company_assets", "company_findings",
          "company_cases", "company_assessments", "company_events"]


def az(*args):
    result = subprocess.run([str(AZ), *args, "-o", "json"], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


@contextmanager
def admin_connection():
    token = az("account", "get-access-token", "--resource", "https://database.windows.net/")["accessToken"]
    raw = token.encode("utf-16-le")
    connection_string = f"Server=tcp:{SERVER}.database.windows.net,1433;Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;"
    with mssql_python.connect(connection_string, attrs_before={1256: struct.pack("<I", len(raw)) + raw}, timeout=60) as connection:
        yield connection


def provision():
    identity = az("webapp", "identity", "show", "-g", GROUP, "-n", APP)["principalId"]
    client_id = az("ad", "sp", "show", "--id", identity)["appId"]
    sid = uuid.UUID(client_id).bytes_le.hex()
    with admin_connection() as connection:
        connection.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        connection.execute(
            f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name=N'{APP}') "
            f"CREATE USER [{APP}] WITH SID=0x{sid}, TYPE=E;"
        )
        for table in TABLES:
            connection.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.[{table}] TO [{APP}];")
    print("Samostatna schema HronTech a opravnenia aplikacie pripravene")


if __name__ == "__main__":
    provision()
