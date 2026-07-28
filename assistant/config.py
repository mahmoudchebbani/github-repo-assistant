"""Typed application settings, read once from the environment or .env."""

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Shared with assistant.search.retrieve so the two cannot enumerate the modes differently.
RetrievalMode = Literal["dense", "lexical", "hybrid"]


class Settings(BaseSettings):
    """Every value the application needs. Required fields have no defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    openai_api_key: str
    openai_model: str
    price_input_per_1m: Decimal
    price_output_per_1m: Decimal
    github_token: str
    repo: str
    ingest_since: date
    docs_globs: str
    embedding_model: str
    chunk_chars: int
    chunk_overlap: int
    retrieval_mode: RetrievalMode
    answer_prompt: Literal["A", "B"]
    top_k: int
    max_retries: int

    @model_validator(mode="after")
    def _check_chunk_overlap(self) -> "Settings":
        """Reject an overlap that would hang or silently drop text in `chunk_text`."""
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_chars ({self.chunk_chars})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded on first call."""
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from the environment
