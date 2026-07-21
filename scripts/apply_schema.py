"""Apply the idempotent CockroachDB schema from DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    schema = Path(__file__).resolve().parents[1].joinpath("schema.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(database_url) as connection:
        connection.execute(schema)
    print("CockroachDB schema applied.")


if __name__ == "__main__":
    main()
