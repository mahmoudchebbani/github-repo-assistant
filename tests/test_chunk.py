from itertools import pairwise

from assistant.chunk import chunk_markdown, chunk_text

PARAGRAPHS = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(10))

MARKDOWN = """# Title

Intro paragraph.

## Installation

Run the installer.

## Usage

Call the function.
"""


def test_every_chunk_respects_the_size_budget():
    chunks = chunk_text(PARAGRAPHS, size=400, overlap=50)
    assert chunks
    assert all(len(chunk) <= 400 for chunk in chunks)


def test_consecutive_chunks_share_their_seam():
    chunks = chunk_text(PARAGRAPHS, size=400, overlap=50)
    assert len(chunks) > 1
    for earlier, later in pairwise(chunks):
        assert earlier[-50:] in later


def test_a_paragraph_longer_than_the_budget_is_split_rather_than_dropped():
    monster = "x" * 1000
    chunks = chunk_text(monster, size=400, overlap=50)
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert sum(chunk.count("x") for chunk in chunks) >= 1000


def test_a_markdown_document_splits_on_its_headings():
    chunks = chunk_markdown(MARKDOWN)
    assert len(chunks) >= 3
    assert any("Installation" in chunk and "Run the installer" in chunk for chunk in chunks)


def test_no_heading_section_is_orphaned_from_its_heading():
    chunks = chunk_markdown(MARKDOWN)
    assert not any(chunk.strip().startswith("Call the function") for chunk in chunks)
