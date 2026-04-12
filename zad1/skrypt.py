import dlt
import pandas as pd
from sqlalchemy import create_engine
import os
from pathlib import Path
from urllib.parse import quote_plus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "SBI2526-LAB-Rating-FixedDate.csv"


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    return normalized in {"1", "true", "t", "yes", "y", "on"}


def _resolve_mssql_url() -> str:
    explicit_dsn = os.getenv("MSSQL_DSN", "").strip()
    if explicit_dsn:
        return explicit_dsn

    host = os.getenv("MSSQL_HOST", "localhost").strip()
    port = os.getenv("MSSQL_PORT", "").strip()
    database = os.getenv("MSSQL_DB", "AdventureWorks2014").strip()
    driver = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    encrypt = os.getenv("MSSQL_ENCRYPT", "no").strip() or "no"
    trust_server_certificate = (
        os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip() or "yes"
    )
    trusted_connection = _env_bool("MSSQL_TRUSTED_CONNECTION", True)

    if not host:
        raise RuntimeError("MSSQL_HOST cannot be empty")

    if "\\" in host or not port:
        server = host
    else:
        server = f"{host},{port}"

    odbc_parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_server_certificate}",
    ]

    if trusted_connection:
        odbc_parts.append("Trusted_Connection=yes")
    else:
        user = os.getenv("MSSQL_USER", "").strip()
        password = os.getenv("MSSQL_PASSWORD", "")
        if not user:
            raise RuntimeError(
                "MSSQL_USER is required when MSSQL_TRUSTED_CONNECTION is false"
            )
        odbc_parts.append(f"UID={user}")
        odbc_parts.append(f"PWD={password}")

    odbc_connection_string = ";".join(odbc_parts) + ";"
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_connection_string)}"


def _resolve_postgres_credentials() -> dict[str, object]:
    return {
        "database": os.getenv("POSTGRES_DB", "postgres"),
        "username": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }


def _resolve_csv_path() -> Path:
    csv_from_env = os.getenv("CSV_PATH", "").strip()
    if csv_from_env:
        return Path(csv_from_env).expanduser().resolve()
    return DEFAULT_CSV_PATH



def extract_products():
    engine = create_engine(_resolve_mssql_url())
    query = "SELECT * FROM Production.Product"
    df = pd.read_sql(query, engine)
    return df


def extract_reviews():
    csv_path = _resolve_csv_path()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    return df


def run():
    load_env_file(PROJECT_ROOT / ".env")

    pipeline = dlt.pipeline(
        pipeline_name="mssql_and_csv_to_postgres",
        destination=dlt.destinations.postgres(credentials=_resolve_postgres_credentials()),
        dataset_name=os.getenv("DLT_DATASET_NAME", "public"),
    )

    products_df = extract_products()
    reviews_df = extract_reviews()

    pipeline.run(
        products_df.to_dict(orient="records"),
        table_name="product",
        write_disposition="replace",
        columns={
            "discontinued_date": {
                "data_type": "timestamp",
                "nullable": True,
            }
        },
    )

    pipeline.run(
        reviews_df.to_dict(orient="records"),
        table_name="reviews",
        write_disposition="replace",
    )


if __name__ == "__main__":
    run()