from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

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


def _build_mysql_dsn_from_parts() -> str | None:
    host = os.getenv("MYSQL_HOST", "localhost").strip()
    port = os.getenv("MYSQL_PORT", "3306").strip() or "3306"
    user = os.getenv("MYSQL_USER", "root").strip()
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DB", "adventureworks2014").strip()

    if not host or not user or not database:
        return None

    safe_user = quote(user, safe="")
    safe_password = quote(password, safe="")
    return f"mysql+pymysql://{safe_user}:{safe_password}@{host}:{port}/{database}"


def _resolve_mysql_dsn() -> str:
    mysql_dsn = os.getenv("MYSQL_DSN", "").strip()
    if mysql_dsn:
        return mysql_dsn

    dsn_from_parts = _build_mysql_dsn_from_parts()
    if dsn_from_parts:
        return dsn_from_parts

    raise RuntimeError(
        "MySQL config is missing. Set MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, "
        "MYSQL_DB in .env or set MYSQL_DSN."
    )


def _quote_mysql_identifier(value: str) -> str:
    return f"`{value.replace('`', '``')}`"


def _table_exists(conn: Connection, schema: str, table: str) -> bool:
    exists = conn.execute(
        text(
            """
            select 1
            from information_schema.tables
            where table_schema = :schema and table_name = :table
            limit 1
            """
        ),
        {"schema": schema, "table": table},
    ).scalar_one_or_none()
    return exists is not None


def _candidate_product_tables(mysql_db: str, preferred_ref: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def add_candidate(schema: str, table: str) -> None:
        if (schema, table) not in candidates:
            candidates.append((schema, table))

    ref = preferred_ref.strip()
    if ref:
        if "." in ref:
            schema, table = ref.split(".", 1)
            add_candidate(schema, table)
            # Some imports keep a literal dotted table name in one database.
            add_candidate(mysql_db, ref)
        else:
            add_candidate(mysql_db, ref)

    add_candidate("production", "product")
    add_candidate(mysql_db, "production.product")
    add_candidate(mysql_db, "production_product")
    add_candidate(mysql_db, "product")

    return candidates


def _resolve_product_table(engine: Engine, mysql_db: str, preferred_ref: str) -> tuple[str, str]:
    candidates = _candidate_product_tables(mysql_db=mysql_db, preferred_ref=preferred_ref)

    with engine.connect() as conn:
        for schema, table in candidates:
            if _table_exists(conn, schema=schema, table=table):
                return schema, table

    checked = ", ".join(f"{schema}.{table}" for schema, table in candidates)
    raise RuntimeError(
        "Could not find Product table in MySQL. "
        f"Checked candidates: {checked}. "
        "Set MYSQL_PRODUCT_TABLE in .env to exact location."
    )


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    by_lower = {col.lower(): col for col in columns}
    for alias in aliases:
        matched = by_lower.get(alias.lower())
        if matched:
            return matched
    return None


def _read_product_table(engine: Engine, mysql_db: str, preferred_ref: str) -> pd.DataFrame:
    schema, table = _resolve_product_table(engine, mysql_db=mysql_db, preferred_ref=preferred_ref)
    qualified_table = f"{_quote_mysql_identifier(schema)}.{_quote_mysql_identifier(table)}"

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

    print(f"Using MySQL table: {schema}.{table} (rows: {len(products)})")
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

    for col in [
        "avg_rating_overall",
        "avg_rating_product",
        "avg_rating_shipping",
        "avg_rating_website",
    ]:
        result[col] = result[col].round(2)

    return result


def _write_output_table(df: pd.DataFrame, engine: Engine, mysql_db: str, output_table: str) -> None:
    out_ref = output_table.strip()
    if not out_ref:
        raise RuntimeError("Output table name cannot be empty")

    if "." in out_ref:
        output_schema, output_name = out_ref.split(".", 1)
    else:
        output_schema, output_name = mysql_db, out_ref

    with engine.begin() as conn:
        conn.execute(text(f"create schema if not exists {_quote_mysql_identifier(output_schema)}"))

    df.to_sql(
        output_name,
        con=engine,
        schema=output_schema,
        if_exists="replace",
        index=False,
        chunksize=1000,
        method="multi",
    )

    print(f"Saved table: {output_schema}.{output_name} (rows: {len(df)})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Join AdventureWorks Product table from MySQL with ratings from CSV and "
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
        "--mysql-db",
        default=os.getenv("MYSQL_DB", "adventureworks2014"),
        help="MySQL database used for output and candidate table lookup",
    )
    parser.add_argument(
        "--product-table",
        default=os.getenv("MYSQL_PRODUCT_TABLE", "production.product"),
        help=(
            "Preferred Product table location (examples: production.product, "
            "adventureworks2014.product, production_product)"
        ),
    )
    parser.add_argument(
        "--output-table",
        default=os.getenv("MYSQL_OUTPUT_TABLE", "analytics.product_rating_from_csv"),
        help="Output table location (example: analytics.product_rating_from_csv)",
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

    mysql_dsn = _resolve_mysql_dsn()
    engine = create_engine(mysql_dsn)

    products = _read_product_table(
        engine=engine,
        mysql_db=args.mysql_db,
        preferred_ref=args.product_table,
    )
    ratings = _read_ratings_csv(args.csv)

    output = ratings.merge(products, on="product_id", how="left", indicator=True)
    output["product_found"] = output["_merge"].eq("both")
    output = output.drop(columns=["_merge"])

    _write_output_table(
        df=output,
        engine=engine,
        mysql_db=args.mysql_db,
        output_table=args.output_table,
    )

    print(output.head(args.limit).to_string(index=False))


if __name__ == "__main__":
    main()