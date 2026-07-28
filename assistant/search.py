"""Retrieval over the chunks table."""

import psycopg
from pgvector import Vector
from psycopg.rows import class_row
from pydantic import BaseModel

from assistant.config import RetrievalMode
from assistant.db import get_connection
from assistant.embed import embed_query

# The one definition of which columns become a Hit; both queries below interpolate it.
_COLUMNS = "id, citation, title, url, text"

_DENSE_QUERY = f"""
    SELECT {_COLUMNS}
    FROM chunks
    ORDER BY embedding <=> %s
    LIMIT %s
"""

_LEXICAL_QUERY = f"""
    SELECT {_COLUMNS}
    FROM chunks
    WHERE lexemes @@ websearch_to_tsquery('english', %s)
    ORDER BY ts_rank_cd(lexemes, websearch_to_tsquery('english', %s)) DESC
    LIMIT %s
"""

RRF_K = 60
# Each leg over-fetches so fusion has more than top_k candidates to combine.
POOL_MULTIPLIER = 4


class Hit(BaseModel):
    """One retrieved chunk."""

    id: str
    citation: str
    title: str
    url: str
    text: str


# Builds a Hit from the query's actual result columns by name, so column order cannot mis-map fields.
_as_hit = class_row(Hit)


def search_dense(conn: psycopg.Connection, query: str, k: int) -> list[Hit]:
    """Return the k nearest chunks by cosine distance."""
    cur = conn.cursor(row_factory=_as_hit)
    return cur.execute(_DENSE_QUERY, (Vector(embed_query(query)), k)).fetchall()


def search_lexical(conn: psycopg.Connection, query: str, k: int) -> list[Hit]:
    """Return the k best chunks by Postgres full-text ranking."""
    cur = conn.cursor(row_factory=_as_hit)
    return cur.execute(_LEXICAL_QUERY, (query, query, k)).fetchall()


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Fuse ranked id lists by summing 1 / (k + rank), rank 1-based."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, identifier in enumerate(ranking, start=1):
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda identifier: -scores[identifier])


def retrieve(query: str, mode: RetrievalMode, top_k: int) -> list[Hit]:
    """Retrieve chunks by dense, lexical, or RRF-fused hybrid search."""
    with get_connection() as conn:
        if mode == "dense":
            return search_dense(conn, query, top_k)
        if mode == "lexical":
            return search_lexical(conn, query, top_k)
        if mode != "hybrid":
            # mode is typed as RetrievalMode; this only fires when a caller passes a raw str anyway.
            raise ValueError(f"unrecognised retrieval mode: {mode!r}")

        pool = top_k * POOL_MULTIPLIER
        dense = search_dense(conn, query, pool)
        lexical = search_lexical(conn, query, pool)
        by_id = {hit.id: hit for hit in dense + lexical}
        fused = reciprocal_rank_fusion([[h.id for h in dense], [h.id for h in lexical]])
        return [by_id[identifier] for identifier in fused[:top_k]]
