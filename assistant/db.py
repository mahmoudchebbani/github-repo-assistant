"""Database connection, schema bootstrap, and the writes behind the monitoring tables."""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector

from assistant.config import get_settings

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()

_TOKENS_PER_PRICED_UNIT = Decimal(1_000_000)

_INSERT_CONVERSATION = """
    INSERT INTO conversations (repo, question, answer, retrieval_mode, attempts)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id
"""

_INSERT_LLM_CALL = """
    INSERT INTO llm_calls
        (conversation_id, node, model, prompt_tokens, completion_tokens, cost_usd, latency_ms)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_FEEDBACK = "INSERT INTO feedback (conversation_id, vote) VALUES (%s, %s)"


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


def cost_usd(prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Price one call from the per-million rates in settings."""
    settings = get_settings()
    return (
        Decimal(prompt_tokens) * settings.price_input_per_1m / _TOKENS_PER_PRICED_UNIT
        + Decimal(completion_tokens) * settings.price_output_per_1m / _TOKENS_PER_PRICED_UNIT
    )


def save_conversation(
    conn: psycopg.Connection,
    repo: str | None,
    question: str,
    answer: str,
    retrieval_mode: str,
    attempts: int,
) -> UUID:
    """Store one answered turn and return its id; repo is NULL when no repository was chosen."""
    row = conn.execute(
        _INSERT_CONVERSATION, (repo, question, answer, retrieval_mode, attempts)
    ).fetchone()
    conn.commit()
    assert row is not None  # RETURNING id on a successful INSERT always yields one row.
    return row[0]


def save_llm_call(
    conn: psycopg.Connection,
    conversation_id: UUID,
    node: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: Decimal,
    latency_ms: int,
) -> None:
    """Store what one model invocation of a turn spent."""
    conn.execute(
        _INSERT_LLM_CALL,
        (conversation_id, node, model, prompt_tokens, completion_tokens, cost, latency_ms),
    )
    conn.commit()


def save_feedback(conn: psycopg.Connection, conversation_id: UUID, vote: int) -> None:
    """Store one thumb, +1 or -1, against the turn it was given on."""
    conn.execute(_INSERT_FEEDBACK, (conversation_id, vote))
    conn.commit()
