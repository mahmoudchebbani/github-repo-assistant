"""Retrieval over the chunks table."""

import psycopg
from pgvector import Vector
from pydantic import BaseModel

from assistant.db import get_connection
from assistant.embed import embed_query

_DENSE_QUERY = """
    SELECT id, citation, title, url, text
    FROM chunks
    ORDER BY embedding <=> %s
    LIMIT %s
"""


class Hit(BaseModel):
    """One retrieved chunk."""

    id: str
    citation: str
    title: str
    url: str
    text: str


def search_dense(conn: psycopg.Connection, query: str, k: int) -> list[Hit]:
    """Return the k nearest chunks by cosine distance."""
    rows = conn.execute(_DENSE_QUERY, (Vector(embed_query(query)), k)).fetchall()
    return [Hit(id=r[0], citation=r[1], title=r[2], url=r[3], text=r[4]) for r in rows]


def retrieve(query: str, mode: str, top_k: int) -> list[Hit]:
    """Retrieve chunks for a query; only `dense` is implemented until Task 6."""
    if mode != "dense":
        raise NotImplementedError(f"retrieval mode {mode!r} arrives in Task 6; use 'dense' for now")
    with get_connection() as conn:
        return search_dense(conn, query, top_k)
