"""Create a dedicated least-privilege CockroachDB database user for the demo."""

from __future__ import annotations

import os
import secrets
from urllib.parse import quote, urlsplit, urlunsplit

DATABASE_NAME = "doream_recall"
APP_USER = "doream_app"


def replace_database_and_user(
    connection_url: str, database: str, user: str, password: str
) -> str:
    parsed = urlsplit(connection_url)
    if not parsed.hostname:
        raise ValueError("CockroachDB connection URL must include a hostname")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}"
    return urlunsplit(
        (parsed.scheme, netloc, f"/{quote(database, safe='')}", parsed.query, "")
    )


def database_url(connection_url: str, database: str) -> str:
    parsed = urlsplit(connection_url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{quote(database, safe='')}", parsed.query, "")
    )


def main() -> None:
    import psycopg
    from psycopg import sql

    admin_url = os.environ.get("COCKROACH_ADMIN_URL")
    if not admin_url:
        raise SystemExit("COCKROACH_ADMIN_URL is required")
    password = secrets.token_urlsafe(32)

    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            "SET CLUSTER SETTING feature.vector_index.enabled = true"
        )
        connection.execute(
            sql.SQL("CREATE DATABASE IF NOT EXISTS {}").format(
                sql.Identifier(DATABASE_NAME)
            )
        )
        connection.execute(
            sql.SQL("CREATE USER IF NOT EXISTS {}").format(sql.Identifier(APP_USER))
        )
        connection.execute(
            sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                sql.Identifier(APP_USER), sql.Literal(password)
            )
        )

    admin_database_url = database_url(admin_url, DATABASE_NAME)
    from pathlib import Path

    schema = Path(__file__).resolve().parents[1].joinpath("schema.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(admin_database_url, autocommit=True) as connection:
        connection.execute(schema)
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(DATABASE_NAME), sql.Identifier(APP_USER)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(APP_USER)
            )
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT ON TABLE dream_memories, reflection_runs TO {}"
            ).format(sql.Identifier(APP_USER))
        )

    print(replace_database_and_user(admin_url, DATABASE_NAME, APP_USER, password))


if __name__ == "__main__":
    main()
