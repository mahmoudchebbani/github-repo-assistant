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

_PULL_REQUESTS_QUERY = """
    SELECT id, number, title, body, html_url
    FROM raw.pull_requests
    WHERE repo = %s
"""

_COMMENTS_QUERY = """
    SELECT id, body, html_url, issue_url
    FROM raw.comments
    WHERE repo = %s
"""

_DOCS_QUERY = """
    SELECT id, path, body, html_url
    FROM raw.docs
    WHERE repo = %s
"""


def read_raw_records(conn: psycopg.Connection, repo: str) -> Iterator[RawRecord]:
    """Yield every ingested row for one repository, across all four source types."""
    for row_id, number, title, body, url in conn.execute(_ISSUES_QUERY, (repo,)):
        yield RawRecord(
            source_type="issue",
            source_id=str(row_id),
            number=number,
            title=title,
            body=body or "",
            url=url,
        )
    for row_id, number, title, body, url in conn.execute(_PULL_REQUESTS_QUERY, (repo,)):
        yield RawRecord(
            source_type="pull_request",
            source_id=str(row_id),
            number=number,
            title=title,
            body=body or "",
            url=url,
        )
    for row_id, body, url, issue_url in conn.execute(_COMMENTS_QUERY, (repo,)):
        number = int(issue_url.rsplit("/", 1)[-1])
        yield RawRecord(
            source_type="comment",
            source_id=str(row_id),
            number=number,
            title=f"Comment on #{number}",
            body=body or "",
            url=url,
        )
    for row_id, path, body, url in conn.execute(_DOCS_QUERY, (repo,)):
        yield RawRecord(
            source_type="doc",
            source_id=str(row_id),
            number=None,
            title=path,
            body=body or "",
            url=url,
            path=path,
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


def reindex(repo: str) -> int:
    """Rebuild one repo's chunks from raw, leaving other repos alone. Returns the count written."""
    settings = get_settings()
    repo = repo.lower()

    # get_connection() raises on a cold DB; bootstrap the schema with a plain connection first.
    with psycopg.connect(settings.database_url) as bootstrap:
        init_db(bootstrap)

    written = 0
    with get_connection() as conn, conn.transaction():
        # Scoped to this repo, not TRUNCATE, so a concurrent reindex of another repo is unaffected.
        conn.execute("DELETE FROM chunks WHERE repo = %s", (repo,))
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
    for repo in get_settings().repo_list():
        reindex(repo)
