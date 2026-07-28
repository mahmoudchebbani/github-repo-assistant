from pgvector import Vector

from assistant.chunk import RawRecord, chunk_record
from assistant.embed import embed_texts
from assistant.search import retrieve


def test_a_record_becomes_a_chunk_that_retrieval_can_find(conn):
    record = RawRecord(
        source_type="issue",
        source_id="1",
        number=42,
        title="Retry policy for the uploader",
        body="We added exponential backoff to the uploader after repeated 503 responses.",
        url="https://github.com/acme/repo/issues/42",
    )
    chunks = chunk_record(record, "acme/repo")
    vectors = embed_texts([c.text for c in chunks])
    for chunk, vector in zip(chunks, vectors):
        conn.execute(
            "INSERT INTO chunks (id, repo, source_type, title, url, citation, text, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                chunk.id,
                chunk.repo,
                chunk.source_type,
                chunk.title,
                chunk.url,
                chunk.citation,
                chunk.text,
                Vector(vector),
            ),
        )
    conn.commit()

    hits = retrieve("what did they do about upload failures", "hybrid", 5)

    assert hits
    assert hits[0].citation == "acme/repo#42"
