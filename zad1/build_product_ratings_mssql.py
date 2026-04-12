from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

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


def _build_mssql_dsn_from_parts(database: str) -> str:
    host = os.getenv("MSSQL_HOST", "localhost").strip()
    port = os.getenv("MSSQL_PORT", "").strip()
    driver = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    encrypt = os.getenv("MSSQL_ENCRYPT", "no").strip() or "no"
    trust_server_certificate = (
        os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip() or "yes"
    )
    trusted_connection = _env_bool("MSSQL_TRUSTED_CONNECTION", True)

    if not host:
        raise RuntimeError("MSSQL_HOST cannot be empty")
    if not database:
        raise RuntimeError("MSSQL database cannot be empty")

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


def _resolve_mssql_dsn(database: str) -> str:
    explicit_dsn = os.getenv("MSSQL_DSN", "").strip()
    if explicit_dsn:
        return explicit_dsn

    return _build_mssql_dsn_from_parts(database=database)


def _quote_sqlserver_identifier(value: str) -> str:
    return f"[{value.replace(']', ']]')}]"


def _parse_table_ref(table_ref: str, default_schema: str = "dbo") -> tuple[str, str]:
    ref = table_ref.strip()
    if not ref:
        raise RuntimeError("Table reference cannot be empty")

    parts = [part for part in ref.split(".") if part]
    if len(parts) == 1:
        return default_schema, parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]

    # If database is included, keep only schema.table.
    return parts[-2], parts[-1]


def _table_exists(conn: Connection, schema: str, table: str) -> bool:
    exists = conn.execute(
        text(
            """
            select 1
            from sys.tables t
            inner join sys.schemas s on s.schema_id = t.schema_id
            where s.name = :schema and t.name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).scalar_one_or_none()
    return exists is not None


def _candidate_product_tables(preferred_ref: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def add_candidate(schema: str, table: str) -> None:
        candidate = (schema, table)
        if candidate not in candidates:
            candidates.append(candidate)

    if preferred_ref.strip():
        add_candidate(*_parse_table_ref(preferred_ref, default_schema="Production"))

    add_candidate("Production", "Product")
    add_candidate("production", "product")
    add_candidate("dbo", "Product")
    add_candidate("dbo", "product")

    return candidates


def _resolve_product_table(engine: Engine, preferred_ref: str) -> tuple[str, str]:
    candidates = _candidate_product_tables(preferred_ref=preferred_ref)

    with engine.connect() as conn:
        for schema, table in candidates:
            if _table_exists(conn, schema=schema, table=table):
                return schema, table

    checked = ", ".join(f"{schema}.{table}" for schema, table in candidates)
    raise RuntimeError(
        "Could not find Product table in SQL Server. "
        f"Checked candidates: {checked}. "
        "Set MSSQL_PRODUCT_TABLE in .env to exact location."
    )


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    by_lower = {column.lower(): column for column in columns}
    for alias in aliases:
        matched = by_lower.get(alias.lower())
        if matched:
            return matched
    return None


def _read_product_table(engine: Engine, preferred_ref: str) -> pd.DataFrame:
    schema, table = _resolve_product_table(engine=engine, preferred_ref=preferred_ref)
    qualified_table = (
        f"{_quote_sqlserver_identifier(schema)}.{_quote_sqlserver_identifier(table)}"
    )
    products_raw = pd.read_sql_query(text(f"select * from {qualified_table}"), con=engine)

    product_columns = list(products_raw.columns)
    product_id_col = _find_column(product_columns, ["ProductID", "product_id", "productid"])
    if not product_id_col:
        raise RuntimeError(
            f"Product table {schema}.{table} does not contain ProductID/product_id column."
        )

    rename_map: dict[str, str] = {product_id_col: "product_id"}
    optional_columns = {
        "product_name": ["Name", "name", "product_name"],
        "product_number": ["ProductNumber", "product_number"],
        "color": ["Color", "color"],
        "standard_cost": ["StandardCost", "standard_cost"],
        "list_price": ["ListPrice", "list_price"],
    }

    for target_name, aliases in optional_columns.items():
        source_col = _find_column(product_columns, aliases)
        if source_col:
            rename_map[source_col] = target_name

    products = products_raw[list(rename_map.keys())].rename(columns=rename_map)
    products["product_id"] = pd.to_numeric(products["product_id"], errors="coerce")
    products = products.dropna(subset=["product_id"]).copy()
    products["product_id"] = products["product_id"].astype("int64")
    products = products.drop_duplicates(subset=["product_id"])

    print(f"Using SQL Server table: {schema}.{table} (rows: {len(products)})")
    return products


def _parse_mixed_date(value: object) -> date | None:
    if value is None:
        return None

    text_value = str(value).strip()
    if not text_value:
        return None

    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text_value, fmt).date()
        except ValueError:
            continue

    return None


def _read_ratings_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

    ratings_raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    required_columns = {
        "productid",
        "date",
        "ratingWebsite",
        "ratingShipping",
        "ratingProduct",
        "ratingOverall",
    }
    missing_columns = required_columns - set(ratings_raw.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise RuntimeError(f"CSV is missing required columns: {missing}")

    ratings = pd.DataFrame(
        {
            "product_id": pd.to_numeric(ratings_raw["productid"], errors="coerce"),
            "review_date": ratings_raw["date"].map(_parse_mixed_date),
            "rating_website": pd.to_numeric(ratings_raw["ratingWebsite"], errors="coerce"),
            "rating_shipping": pd.to_numeric(ratings_raw["ratingShipping"], errors="coerce"),
            "rating_product": pd.to_numeric(ratings_raw["ratingProduct"], errors="coerce"),
            "rating_overall": pd.to_numeric(ratings_raw["ratingOverall"], errors="coerce"),
        }
    )

    ratings = ratings.dropna(subset=["product_id"]).copy()
    ratings["product_id"] = ratings["product_id"].astype("int64")

    result = (
        ratings.groupby("product_id", as_index=False)
        .agg(
            reviews_count=("product_id", "size"),
            first_review_date=("review_date", "min"),
            last_review_date=("review_date", "max"),
            avg_rating_overall=("rating_overall", "mean"),
            avg_rating_product=("rating_product", "mean"),
            avg_rating_shipping=("rating_shipping", "mean"),
            avg_rating_website=("rating_website", "mean"),
        )
        .sort_values(["reviews_count", "product_id"], ascending=[False, True])
        .reset_index(drop=True)
    )

    for column in [
        "avg_rating_overall",
        "avg_rating_product",
        "avg_rating_shipping",
        "avg_rating_website",
    ]:
        result[column] = result[column].round(2)

    return result


def _ensure_schema_exists(conn: Connection, schema: str) -> None:
    exists = conn.execute(
        text("select 1 from sys.schemas where name = :schema"),
        {"schema": schema},
    ).scalar_one_or_none()

    if exists is None:
        conn.execute(text(f"create schema {_quote_sqlserver_identifier(schema)}"))


def _write_output_table(df: pd.DataFrame, engine: Engine, output_table: str) -> None:
    output_schema, output_name = _parse_table_ref(output_table, default_schema="dbo")

    with engine.begin() as conn:
        _ensure_schema_exists(conn=conn, schema=output_schema)

    df.to_sql(
        output_name,
        con=engine,
        schema=output_schema,
        if_exists="replace",
        index=False,
        chunksize=200,
    )

    print(f"Saved table: {output_schema}.{output_name} (rows: {len(df)})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Join AdventureWorks Product table from SQL Server with ratings from CSV and "
            "create a new output table"
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to ratings CSV file",
    )
    parser.add_argument(
        "--mssql-db",
        default=os.getenv("MSSQL_DB", "AdventureWorks2014"),
        help="SQL Server database name",
    )
    parser.add_argument(
        "--product-table",
        default=os.getenv("MSSQL_PRODUCT_TABLE", "Production.Product"),
        help="Product table reference (example: Production.Product)",
    )
    parser.add_argument(
        "--output-table",
        default=os.getenv("MSSQL_OUTPUT_TABLE", "dbo.product_rating_from_csv"),
        help="Output table reference (example: dbo.product_rating_from_csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of output rows to print",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(PROJECT_ROOT / ".env")
    args = parse_args()

    mssql_dsn = _resolve_mssql_dsn(database=args.mssql_db)
    engine = create_engine(
        mssql_dsn,
        fast_executemany=True,
        use_insertmanyvalues=False,
    )

    products = _read_product_table(engine=engine, preferred_ref=args.product_table)
    ratings = _read_ratings_csv(args.csv)

    output = ratings.merge(products, on="product_id", how="left", indicator=True)
    output["product_found"] = output["_merge"].eq("both")
    output = output.drop(columns=["_merge"])

    _write_output_table(df=output, engine=engine, output_table=args.output_table)

    print(output.head(args.limit).to_string(index=False))


if __name__ == "__main__":
    main()