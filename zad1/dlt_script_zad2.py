import dlt
import pandas as pd
import requests
from sqlalchemy import create_engine
from pathlib import Path
from datetime import date, timedelta

# configuracja

DATE_SHIFT_YEARS = 11       # TU TRZEBA DOSTOSOWAĆ
CURRENCY = "EUR"
NBP_YEARS = 4
TARGET_SCHEMA = "extract"

CSV_PATH = Path(dlt.secrets["sources.csv_reviews.path"]).resolve()


def get_engine():
    return create_engine(dlt.secrets["sources.mssql.connection_string"])


def read_table(engine, query: str) -> pd.DataFrame:
    return pd.read_sql(query, engine)


def shift_date_columns(df: pd.DataFrame, columns: list[str], years: int) -> pd.DataFrame:
    offset = pd.DateOffset(years=years)
    for col in columns:
        if col in df.columns and df[col].notna().any():
            df[col] = pd.to_datetime(df[col]) + offset
    return df


# EKSTRAKCJA Z MSSQL

def extract_mssql_tables(engine) -> dict[str, pd.DataFrame]:
    plain_tables = {
        "product":             "SELECT * FROM Production.Product",
        "product_subcategory": "SELECT * FROM Production.ProductSubcategory",
        "product_category":    "SELECT * FROM Production.ProductCategory",

        "product_cost_history":"SELECT * FROM Production.ProductCostHistory",

        "salesperson":         "SELECT * FROM Sales.SalesPerson",
        
        "sales_territory":     "SELECT * FROM Sales.SalesTerritory",

        "person":              "SELECT * FROM Person.Person",

        "country_region":      "SELECT * FROM Person.CountryRegion",
    }

    result: dict[str, pd.DataFrame] = {}

    for name, sql in plain_tables.items():
        result[name] = read_table(engine, sql)


    soh = read_table(engine, "SELECT * FROM Sales.SalesOrderHeader")
    soh = shift_date_columns(
        soh,
        ["OrderDate", "DueDate", "ShipDate", "ModifiedDate"],
        DATE_SHIFT_YEARS,
    )
    result["sales_order_header"] = soh

    sod = read_table(engine, "SELECT * FROM Sales.SalesOrderDetail")
    sod = shift_date_columns(sod, ["ModifiedDate"], DATE_SHIFT_YEARS)
    result["sales_order_detail"] = sod

    return result


# ŁADOWANIE CSV

def extract_reviews() -> pd.DataFrame:
    """
    reviewid, productid, date, ratingWebsite, ratingShipping, ratingProduct, 
    ratingOverall, gender, email, job, postCode, source, didPurchase, 
    didRecommend, isUsefull, userAgent, ip
    """
    df = pd.read_csv(CSV_PATH)
    return df


# FETCHING KURSÓW

def fetch_nbp_rates(currency: str = CURRENCY, years: int = NBP_YEARS) -> pd.DataFrame:
    end_date = date.today()
    start_date = end_date - timedelta(days=years * 365)

    records: list[dict] = []
    chunk_start = start_date
    MAX_DAYS = 366  # NBP hard limit per request

    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=MAX_DAYS), end_date)

        url = (
            f"http://api.nbp.pl/api/exchangerates/rates/a"
            f"/{currency}"
            f"/{chunk_start.strftime('%Y-%m-%d')}"
            f"/{chunk_end.strftime('%Y-%m-%d')}/"
        )

        response = requests.get(url, headers={"Accept": "application/json"}, timeout=15)

        if response.status_code == 200:
            payload = response.json()
            for rate in payload["rates"]:
                records.append(
                    {
                        "currency_code": payload["code"],
                        "currency_name": payload["currency"],
                        "table_no":      rate["no"],
                        "effective_date": rate["effectiveDate"],
                        "mid_rate":      rate["mid"],
                    }
                )
        else:
            print(f"UWAGA: NBI zwróciło {response.status_code} dla {chunk_start} - {chunk_end}")

        chunk_start = chunk_end + timedelta(days=1)

    df = pd.DataFrame(records)
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
    return df


# PIPELINE

pipeline = dlt.pipeline(
    pipeline_name="adventureworks_star_extract",
    destination="postgres",
    dataset_name=TARGET_SCHEMA,    # tworzy scheme extracted 
)



def main():
    engine = get_engine()

    print("=== EKSTRAKCJA MSSQL ===")
    mssql_tables = extract_mssql_tables(engine)

    for table_name, df in mssql_tables.items():
        print(f"Ładowanie MSSQL {table_name} ({len(df)} wierszy)")
        pipeline.run(
            df,
            table_name=table_name,
            write_disposition="replace",
        )

    print("=== ŁADOWANIE CSV ===")
    reviews_df = extract_reviews()
    print(f"długość scv: {len(reviews_df)}")
    pipeline.run(
        reviews_df,
        table_name="ProductRating",
        write_disposition="replace",
    )

    print("=== FETCHING Z NBP ===")
    rates_df = fetch_nbp_rates()
    print(f"pobrano {len(rates_df)} rekordów")
    pipeline.run(
        rates_df,
        table_name="CurrencyRateData",
        write_disposition="replace",
    )

    print("=== === ===")
    print("WYNIKI:")
    print(pipeline.last_trace)


if __name__ == "__main__":
    main()
