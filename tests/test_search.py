import pytest
from pgvector import Vector

from assistant.embed import embed_texts
from assistant.search import search_dense, search_lexical

DOCUMENTS = [
    ("d1", "acme/repo#1", "Async client rewrite", "The client was rewritten to be asynchronous."),
    ("d2", "acme/repo#2", "Flaky CI", "Windows runners intermittently fail with ETIMEDOUT."),
    ("d3", "acme/repo#3", "Release notes", "Version 2.0 drops Python 3.8 support."),
]


@pytest.fixture
def populated(conn):
    vectors = embed_texts([text for _, _, _, text in DOCUMENTS])
    for (identifier, citation, title, text), vector in zip(DOCUMENTS, vectors):
        conn.execute(
            "INSERT INTO chunks (id, repo, source_type, title, url, citation, text, embedding)"
            " VALUES (%s, 'acme/repo', 'issue', %s, 'http://x', %s, %s, %s)",
            (identifier, title, citation, text, Vector(vector)),
        )
    conn.commit()
    return conn


def test_dense_search_finds_a_paraphrase_that_lexical_search_would_miss(populated):
    hits = search_dense(populated, "why did they move to a non-blocking client", k=3)
    assert hits[0].id == "d1"


def test_lexical_search_finds_an_exact_token_dense_search_would_blur(populated):
    hits = search_lexical(populated, "ETIMEDOUT", k=3)
    assert [hit.id for hit in hits] == ["d2"]
