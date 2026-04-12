# dlt + dbt + PostgreSQL (localhost)

Ten projekt laduje dane z CSV do PostgreSQL przez dlt, a potem buduje proste modele przez dbt.

Plik wejsciowy:
- `zad1/SBI2526-LAB-Rating-FixedDate.csv`

## 1. Konfiguracja

1. Skopiuj `.env.example` do `.env` i ustaw dane logowania do lokalnego PostgreSQL.
2. Zainstaluj zaleznosci:

```powershell
uv sync
```

## 2. Zaladowanie CSV przez dlt

```powershell
python zad1/load_ratings_dlt.py
```

Opcjonalnie mozesz podac inna nazwe schematu docelowego:

```powershell
python zad1/load_ratings_dlt.py --dataset lab5_raw
```

## 3. Uruchomienie dbt

```powershell
dbt debug --project-dir zad1/dbt_rating --profiles-dir zad1/dbt_rating
dbt run --project-dir zad1/dbt_rating --profiles-dir zad1/dbt_rating
dbt test --project-dir zad1/dbt_rating --profiles-dir zad1/dbt_rating
```

## 4. Uruchomienie wszystkiego jednym poleceniem

```powershell
python zad1/run_pipeline.py
```

## Co powstaje w bazie

Po dlt:
- schema `${DLT_DATASET_NAME}` (domyslnie `lab5_raw`)
- tabela `ratings`

Po dbt:
- schema `${DBT_SCHEMA}` (domyslnie `analytics`)
- model `stg_ratings`
- model `product_rating_summary`

## 5. Przykład: MySQL AdventureWorks + CSV -> nowa tabela

Skrypt:
- `zad1/build_product_ratings_mysql.py`

Co robi:
1. Laczy sie do MySQL (`MYSQL_*` z `.env`).
2. Pobiera tabele Product (domyslnie `production.product`, z fallbackami).
3. Liczy agregaty ocen z CSV po `product_id`.
4. Laczy dane Product + agregaty ocen.
5. Zapisuje wynik do nowej tabeli MySQL (domyslnie `analytics.product_rating_from_csv`).

Uruchomienie:

```powershell
python zad1/build_product_ratings_mysql.py
```

Przyklad z parametrami:

```powershell
python zad1/build_product_ratings_mysql.py --mysql-db adventureworks2014 --product-table production.product --output-table analytics.product_rating_from_csv
```

Szybka weryfikacja w MySQL:

```sql
SELECT COUNT(*) FROM analytics.product_rating_from_csv;
SELECT *
FROM analytics.product_rating_from_csv
ORDER BY reviews_count DESC, product_id
LIMIT 10;
```

## 6. Przykład: SQL Server AdventureWorks2014 + CSV -> nowa tabela

Skrypt:
- `zad1/build_product_ratings_mssql.py`

Co robi:
1. Laczy sie do SQL Server (`MSSQL_*` z `.env`).
2. Pobiera `Production.Product` z bazy `AdventureWorks2014`.
3. Liczy agregaty ocen z CSV po `product_id`.
4. Laczy Product + agregaty ocen.
5. Zapisuje wynik do nowej tabeli SQL Server (domyslnie `dbo.product_rating_from_csv`).

Uruchomienie:

```powershell
python zad1/build_product_ratings_mssql.py
```

Uwagi konfiguracyjne:
- Lokalny SQL Server czesto nie nasluchuje na TCP 1433. W takim przypadku zostaw `MSSQL_PORT=` puste w `.env`.

Przyklad z parametrami:

```powershell
python zad1/build_product_ratings_mssql.py --mssql-db AdventureWorks2014 --product-table Production.Product --output-table dbo.product_rating_from_csv
```

Szybka weryfikacja w SQL Server:

```sql
SELECT COUNT(*) FROM dbo.product_rating_from_csv;
SELECT TOP 10 *
FROM dbo.product_rating_from_csv
ORDER BY reviews_count DESC, product_id;
```

## 7. dbt pod nowy pipeline (`skrypt.py`)

Po uruchomieniu `python zad1/skrypt.py` masz w Postgresie tabele:
- `lab5_raw.product`
- `lab5_raw.reviews`

Dodane modele dbt:
- staging: `stg_product`, `stg_reviews`
- marts: `product_reviews_enriched`, `product_reviews_summary_mssql`

Uruchomienie tylko nowych modeli:

```powershell
python -m dbt.cli.main run --project-dir zad1/dbt_rating --profiles-dir zad1/dbt_rating --select stg_product stg_reviews product_reviews_enriched product_reviews_summary_mssql
python -m dbt.cli.main test --project-dir zad1/dbt_rating --profiles-dir zad1/dbt_rating --select stg_product stg_reviews product_reviews_summary_mssql
```