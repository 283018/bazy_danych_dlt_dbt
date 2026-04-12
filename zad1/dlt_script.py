import dlt
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path


# -----------
# Odpalić za pierwszym razem
# -----------

# import pyarrow
# pyarrow.util.download_tzdata_on_windows()


CSV_PATH = Path(dlt.secrets["sources.csv_reviews.path"]).resolve()

def extract_products():
    engine = create_engine(dlt.secrets["sources.mssql.connection_string"])
    query = "SELECT * FROM Production.Product"
    df = pd.read_sql(query, engine)
    return df


def extract_reviews():
    df = pd.read_csv(CSV_PATH)
    return df


pipeline = dlt.pipeline(
    pipeline_name="mssql_and_csv_to_postgres",
    destination="postgres",
    dataset_name="public",
)


def run():
    products_df = extract_products()
    reviews_df = extract_reviews()

    pipeline.run(
        products_df,
        table_name="product",
        write_disposition="replace",
    )

    pipeline.run(
        reviews_df,
        table_name="reviews",
        write_disposition="replace",
    )


if __name__ == "__main__":
    run()
