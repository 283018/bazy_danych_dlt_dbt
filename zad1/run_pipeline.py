from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from load_ratings_dlt import DEFAULT_CSV_PATH, PROJECT_ROOT, load_env_file, run_pipeline

DBT_PROJECT_DIR = Path(__file__).resolve().parent / "dbt_rating"


def _run_command(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def _run_dbt() -> None:
    if not DBT_PROJECT_DIR.exists():
        raise FileNotFoundError(f"dbt project directory does not exist: {DBT_PROJECT_DIR}")

    common_args = [
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
    ]

    dbt_cmd = [sys.executable, "-m", "dbt.cli.main"]

    _run_command([*dbt_cmd, "debug", *common_args])
    _run_command([*dbt_cmd, "run", *common_args])
    _run_command([*dbt_cmd, "test", *common_args])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load CSV with dlt and run dbt models on PostgreSQL"
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
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Run only dlt load without dbt",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(PROJECT_ROOT / ".env")
    args = parse_args()

    run_pipeline(csv_path=args.csv, dataset_name=args.dataset)

    if not args.skip_dbt:
        _run_dbt()


if __name__ == "__main__":
    main()