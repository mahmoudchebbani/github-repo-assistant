"""Database connection and schema bootstrap."""

from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from assistant.config import get_settings

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def get_connection() -> psycopg.Connection:
    """Open a connection with pgvector's types registered on it."""
    # Raises ProgrammingError on a cold database: register_vector needs the vector
    # type in the catalogue, which only exists after init_db has run. To bootstrap,
    # connect with psycopg.connect directly, call init_db, then use this.
    conn = psycopg.connect(get_settings().database_url)
    register_vector(conn)
    return conn


def init_db(conn: psycopg.Connection) -> None:
    """Create every table, extension and index if it does not already exist."""
    conn.execute(_SCHEMA.encode())
    conn.commit()
