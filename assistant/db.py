"""Database connection and schema bootstrap."""

from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from assistant.config import get_settings

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def get_connection() -> psycopg.Connection:
    """Open a connection with pgvector's types registered on it."""
    # Raises ProgrammingError on a cold DB; bootstrap with plain psycopg.connect + init_db first.
    conn = psycopg.connect(get_settings().database_url)
    register_vector(conn)
    return conn


def init_db(conn: psycopg.Connection) -> None:
    """Create every table, extension and index if it does not already exist."""
    conn.execute(_SCHEMA.encode())
    conn.commit()
