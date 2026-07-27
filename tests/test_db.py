def test_the_schema_creates_pgvector_and_the_chunks_table(conn):
    extensions = conn.execute("SELECT extname FROM pg_extension").fetchall()
    assert ("vector",) in extensions

    columns = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'chunks'"
    ).fetchall()
    assert ("embedding",) in columns
    assert ("lexemes",) in columns
