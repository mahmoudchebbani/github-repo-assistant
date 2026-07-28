from decimal import Decimal

from assistant.db import cost_usd, save_conversation, save_feedback, save_llm_call


def test_the_schema_creates_pgvector_and_the_chunks_table(conn):
    extensions = conn.execute("SELECT extname FROM pg_extension").fetchall()
    assert ("vector",) in extensions

    columns = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'chunks'"
    ).fetchall()
    assert ("embedding",) in columns
    assert ("lexemes",) in columns


def test_a_conversation_and_its_call_round_trip(conn):
    conversation_id = save_conversation(conn, "acme/repo", "q?", "a.", "hybrid", 2)
    save_llm_call(
        conn, conversation_id, "generate", "gpt-4o-mini", 1000, 500, Decimal("0.0004500000"), 812
    )

    stored = conn.execute(
        "SELECT cost_usd, latency_ms FROM llm_calls WHERE conversation_id = %s",
        (conversation_id,),
    ).fetchone()

    assert stored[0] == Decimal("0.0004500000")
    assert isinstance(stored[0], Decimal)
    assert stored[1] == 812


def test_a_sub_cent_cost_does_not_round_to_zero(conn):
    conversation_id = save_conversation(conn, "acme/repo", "q?", "a.", "dense", 1)
    tiny = cost_usd(prompt_tokens=3, completion_tokens=1)
    save_llm_call(conn, conversation_id, "grade", "gpt-4o-mini", 3, 1, tiny, 40)

    stored = conn.execute(
        "SELECT cost_usd FROM llm_calls WHERE conversation_id = %s", (conversation_id,)
    ).fetchone()
    assert stored[0] > 0


def test_feedback_is_linked_to_its_conversation(conn):
    conversation_id = save_conversation(conn, "acme/repo", "q?", "a.", "hybrid", 1)
    save_feedback(conn, conversation_id, 1)
    votes = conn.execute(
        "SELECT vote FROM feedback WHERE conversation_id = %s", (conversation_id,)
    ).fetchall()
    assert votes == [(1,)]
