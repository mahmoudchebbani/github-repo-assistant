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


# Requiring every term matched 47 of 50 evaluation questions nowhere, which made hybrid decorative.
def test_lexical_search_ranks_on_overlap_rather_than_demanding_every_term(populated):
    hits = search_lexical(populated, "why do the Windows runners keep failing", k=3)
    assert hits[0].id == "d2"


def test_a_question_of_only_stopwords_retrieves_nothing_lexically(populated):
    assert search_lexical(populated, "what is the it of a to", k=3) == []


# Repo filtering is new SQL predicate logic with no other coverage; a silent bug here would leak
# one repo's chunks into another's results without raising, so it earns the one extra test allowed.
def test_repo_filter_keeps_a_matching_chunk_from_another_repo_out_of_scope(populated):
    text = "Windows runners intermittently fail with ETIMEDOUT."
    vector = embed_texts([text])[0]
    populated.execute(
        "INSERT INTO chunks (id, repo, source_type, title, url, citation, text, embedding)"
        " VALUES ('d4', 'other/repo', 'issue', 'Flaky CI', 'http://x', 'other/repo#1', %s, %s)",
        (text, Vector(vector)),
    )
    populated.commit()

    dense_hits = search_dense(populated, "ETIMEDOUT", k=5, repo="acme/repo")
    lexical_hits = search_lexical(populated, "ETIMEDOUT", k=5, repo="acme/repo")
    assert all(hit.id != "d4" for hit in dense_hits)
    assert [hit.id for hit in lexical_hits] == ["d2"]
