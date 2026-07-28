"""Raw records into retrievable chunks: packing, ids and citations."""

import hashlib
from typing import Literal

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser
from pydantic import BaseModel

from assistant.config import get_settings

_MARKDOWN_PARSER = MarkdownNodeParser()

PARAGRAPH_SEPARATOR = "\n\n"
ID_HASH_LENGTH = 12


class RawRecord(BaseModel):
    """One ingested row, normalised across the four source types."""

    source_type: Literal["issue", "pull_request", "comment", "doc"]
    source_id: str
    number: int | None
    title: str
    body: str
    url: str
    path: str | None = None


class Chunk(BaseModel):
    """One indexable span of text with everything needed to cite it."""

    id: str
    repo: str
    source_type: str
    title: str
    url: str
    citation: str
    text: str


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Pack paragraphs greedily, in source order, into spans of at most `size` characters."""
    chunks: list[str] = []
    current = ""
    for paragraph in text.split(PARAGRAPH_SEPARATOR):
        current = f"{current}{PARAGRAPH_SEPARATOR}{paragraph}" if current else paragraph
        while len(current) > size:
            chunks.append(current[:size])
            current = current[size - overlap :]
    if current:
        chunks.append(current)
    return chunks


def build_citation(record: RawRecord, repo: str) -> str:
    """Return `owner/repo#123` for discussion, `owner/repo:path` for docs."""
    if record.source_type == "doc":
        return f"{repo}:{record.path}"
    return f"{repo}#{record.number}"


def build_chunk_id(record: RawRecord, ordinal: int) -> str:
    """Return a stable id for one chunk of one source record."""
    # A doc's source_id is a content-addressed git blob SHA; identical files collide, so use path.
    key = record.path if record.source_type == "doc" else record.source_id
    seed = f"{record.source_type}:{key}:{ordinal}"
    return hashlib.sha256(seed.encode()).hexdigest()[:ID_HASH_LENGTH]


def chunk_markdown(text: str) -> list[str]:
    """Split a markdown document into sections along its heading structure."""
    nodes = _MARKDOWN_PARSER.get_nodes_from_documents([Document(text=text)])
    return [node.get_content() for node in nodes if node.get_content().strip()]


def chunk_record(record: RawRecord, repo: str) -> list[Chunk]:
    """Split one raw record into chunks; a title-only body still yields one chunk, not zero."""
    settings = get_settings()
    if record.source_type == "doc":
        # A heading section can itself exceed the token window, so re-pack each one by size.
        sections = chunk_markdown(record.body)
        texts = [
            piece
            for section in sections
            for piece in chunk_text(section, settings.chunk_chars, settings.chunk_overlap)
        ] or [""]
    else:
        texts = chunk_text(record.body, settings.chunk_chars, settings.chunk_overlap) or [""]
    citation = build_citation(record, repo)
    return [
        Chunk(
            id=build_chunk_id(record, ordinal),
            repo=repo,
            source_type=record.source_type,
            title=record.title,
            url=record.url,
            citation=citation,
            text=f"{record.title}{PARAGRAPH_SEPARATOR}{text}" if text else record.title,
        )
        for ordinal, text in enumerate(texts)
    ]
