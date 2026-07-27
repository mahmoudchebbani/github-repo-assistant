"""Read raw rows, chunk them, embed them, and rebuild the chunks table."""

from collections.abc import Iterator

import psycopg
from pgvector import Vector

from assistant.chunk import Chunk, RawRecord, chunk_record
from assistant.config import get_settings
from assistant.db import get_connection, init_db
from assistant.embed import embed_texts

BATCH_SIZE = 128

_ISSUES_QUERY = """
    SELECT id, number, title, body, html_url
    FROM raw.issues
    WHERE repo = %s
"""


def read_raw_records(conn: psycopg.Connection, repo: str) -> Iterator[RawRecord]:
    """Yield every ingested row for one repository as a normalised record."""
    for row_id, number, title, body, url in conn.execute(_ISSUES_QUERY, (repo,)):
        yield RawRecord(
            source_type="issue",
            source_id=str(row_id),
            number=number,
            title=title,
            body=body or "",
            url=url,
        )


def _write(conn: psycopg.Connection, chunks: list[Chunk]) -> None:
    vectors = embed_texts([chunk.text for chunk in chunks])
    conn.cursor().executemany(
        """
        INSERT INTO chunks (id, repo, source_type, title, url, citation, text, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            (c.id, c.repo, c.source_type, c.title, c.url, c.citation, c.text, Vector(v))
            for c, v in zip(chunks, vectors)
        ],
    )


def reindex() -> int:
    """Rebuild the chunks table from raw. Returns the number of chunks written."""
    settings = get_settings()
    repo = settings.repo.lower()

    # get_connection() calls register_vector, which raises ProgrammingError until
    # `vector` is in the catalogue. Bootstrap the schema with a plain connection first,
    # then switch to the pgvector-registered one for the real work.
    with psycopg.connect(settings.database_url) as bootstrap:
        init_db(bootstrap)

    written = 0
    with get_connection() as conn, conn.transaction():
        conn.execute("TRUNCATE chunks")
        batch: list[Chunk] = []
        for record in read_raw_records(conn, repo):
            batch.extend(chunk_record(record, repo))
            if len(batch) >= BATCH_SIZE:
                _write(conn, batch)
                written += len(batch)
                batch = []
        if batch:
            _write(conn, batch)
            written += len(batch)
    print(f"indexed {written} chunks for {repo}")
    return written


if __name__ == "__main__":
    reindex()
