"""A throwaway pgvector container, shared by every test that needs a database."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from testcontainers.community.postgres import PostgresContainer

from assistant.config import get_settings
from assistant.db import init_db


@pytest.fixture(scope="session", autouse=True)
def _environment() -> Iterator[None]:
    load_dotenv(".env.test", override=True)
    with PostgresContainer("pgvector/pgvector:pg17", driver=None) as container:
        os.environ["DATABASE_URL"] = container.get_connection_url()
        get_settings.cache_clear()
        yield


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(os.environ["DATABASE_URL"])
    init_db(connection)
    register_vector(connection)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.execute("TRUNCATE chunks, conversations CASCADE")
        connection.commit()
        connection.close()
