"""Raw records into retrievable chunks: packing, ids and citations."""

import hashlib
from typing import Literal

from pydantic import BaseModel

from assistant.config import get_settings

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
    """Pack paragraphs greedily into spans of at most `size` characters."""
    chunks: list[str] = []
    current = ""
    for paragraph in text.split(PARAGRAPH_SEPARATOR):
        while len(paragraph) > size:
            chunks.append(paragraph[:size])
            paragraph = paragraph[size - overlap :]
        candidate = f"{current}{PARAGRAPH_SEPARATOR}{paragraph}" if current else paragraph
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = f"{current[-overlap:]}{paragraph}" if current else paragraph
        if len(current) > size:
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
    seed = f"{record.source_type}:{record.source_id}:{ordinal}"
    return hashlib.sha256(seed.encode()).hexdigest()[:ID_HASH_LENGTH]


def chunk_record(record: RawRecord, repo: str) -> list[Chunk]:
    """Split one raw record into chunks, each carrying its own citation."""
    settings = get_settings()
    texts = chunk_text(record.body, settings.chunk_chars, settings.chunk_overlap)
    citation = build_citation(record, repo)
    return [
        Chunk(
            id=build_chunk_id(record, ordinal),
            repo=repo,
            source_type=record.source_type,
            title=record.title,
            url=record.url,
            citation=citation,
            text=f"{record.title}\n\n{text}",
        )
        for ordinal, text in enumerate(texts)
    ]
