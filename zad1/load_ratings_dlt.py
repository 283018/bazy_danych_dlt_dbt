from __future__ import annotations

import argparse
import csv
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlparse

import dlt

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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _build_postgres_dsn_from_parts() -> str | None:
    host = os.getenv("POSTGRES_HOST", "").strip()
    port = os.getenv("POSTGRES_PORT", "5432").strip() or "5432"
    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "").strip()

    if not host or not user or not database:
        return None

    safe_user = quote(user, safe="")
    safe_password = quote(password, safe="")
    return f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{database}"


def _resolve_postgres_dsn() -> str:
    postgres_dsn = os.getenv("POSTGRES_DSN", "").strip()

    # Prefer composing DSN from POSTGRES_* values to avoid URI parsing issues
    # with special characters in passwords (for example '@').
    dsn_from_parts = _build_postgres_dsn_from_parts()
    if dsn_from_parts:
        return dsn_from_parts

    if postgres_dsn:
        parsed = urlparse(postgres_dsn)
        if parsed.hostname and "@" in parsed.hostname:
            raise RuntimeError(
                "POSTGRES_DSN is invalid (looks like unescaped '@' in password). "
                "Use POSTGRES_PASSWORD and POSTGRES_* fields or replace '@' with '%40' in POSTGRES_DSN."
            )
        return postgres_dsn

    raise RuntimeError(
        "PostgreSQL config is missing. Set POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, "
        "POSTGRES_PASSWORD, POSTGRES_DB in .env (recommended) or provide POSTGRES_DSN."
    )


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if normalized == "":
        return None
    return normalized in {"1", "true", "t", "yes", "y"}


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    return int(float(text))


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def _parse_date(value: Any) -> date | None:
    text = _clean_text(value)
    if text is None:
        return None

    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {text}")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    review_id_value = row.get("reviewid")
    if review_id_value is None:
        review_id_value = row.get("\ufeffreviewid")

    return {
        "review_id": _parse_int(review_id_value),
        "product_id": _parse_int(row.get("productid")),
        "review_date": _parse_date(row.get("date")),
        "rating_website": _parse_float(row.get("ratingWebsite")),
        "rating_shipping": _parse_float(row.get("ratingShipping")),
        "rating_product": _parse_float(row.get("ratingProduct")),
        "rating_overall": _parse_float(row.get("ratingOverall")),
        "gender": _clean_text(row.get("gender")),
        "email": _clean_text(row.get("email")),
        "job": _clean_text(row.get("job")),
        "post_code": _clean_text(row.get("postCode")),
        "source": _clean_text(row.get("source")),
        "did_purchase": _parse_bool(row.get("didPurchase")),
        "did_recommend": _parse_bool(row.get("didRecommend")),
        "is_useful_votes": _parse_int(row.get("isUsefull")),
        "user_agent": _clean_text(row.get("userAgent")),
        "ip": _clean_text(row.get("ip")),
    }


@dlt.resource(name="ratings", write_disposition="replace")
def ratings_resource(csv_path: str) -> Iterator[dict[str, Any]]:
    with Path(csv_path).open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            yield _normalize_row(row)


def run_pipeline(csv_path: Path, dataset_name: str) -> None:
    load_env_file(PROJECT_ROOT / ".env")

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

    postgres_dsn = _resolve_postgres_dsn()

    os.environ.setdefault("DESTINATION__POSTGRES__CREDENTIALS", postgres_dsn)

    pipeline = dlt.pipeline(
        pipeline_name="ratings_csv_pipeline",
        destination="postgres",
        dataset_name=dataset_name,
        progress="log",
    )

    load_info = pipeline.run(ratings_resource(str(csv_path)))
    print(load_info)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load ratings CSV into localhost PostgreSQL using dlt"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to input CSV file",
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv("DLT_DATASET_NAME", "lab5_raw"),
        help="PostgreSQL schema name used by dlt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(csv_path=args.csv, dataset_name=args.dataset)


if __name__ == "__main__":
    main()