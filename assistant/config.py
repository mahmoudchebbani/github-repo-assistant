"""Typed application settings, read once from the environment or .env."""

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Shared with assistant.search.retrieve so the two cannot enumerate the modes differently.
RetrievalMode = Literal["dense", "lexical", "hybrid"]


class Settings(BaseSettings):
    """Every value the application needs. Required fields have no defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # min_length so a blank key raises at startup, not as a 401 after the user has waited.
    openai_api_key: str = Field(min_length=1)
    openai_model: str
    price_input_per_1m: Decimal
    price_output_per_1m: Decimal
    github_token: str = Field(min_length=1)
    repos: str
    ingest_since: date
    docs_globs: str
    embedding_model: str
    chunk_chars: int
    chunk_overlap: int
    retrieval_mode: RetrievalMode
    answer_prompt: Literal["A", "B"]
    top_k: int = Field(ge=1)
    max_retries: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_chunk_overlap(self) -> "Settings":
        """Reject an overlap that would hang or silently drop text in `chunk_text`."""
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_chars ({self.chunk_chars})"
            )
        return self

    @model_validator(mode="after")
    def _check_repos_not_empty(self) -> "Settings":
        """Reject a REPOS value that parses to no repository at all."""
        if not self.repo_list():
            raise ValueError(f"REPOS ({self.repos!r}) must name at least one repository")
        return self

    @model_validator(mode="after")
    def _check_docs_globs_not_empty(self) -> "Settings":
        """Reject a DOCS_GLOBS value that parses to no pattern, which would ingest zero docs."""
        if not self.docs_globs_list():
            raise ValueError(f"DOCS_GLOBS ({self.docs_globs!r}) must name at least one pattern")
        return self

    def repo_list(self) -> list[str]:
        """Return REPOS split on commas, lower-cased and stripped, blanks dropped."""
        return [repo.strip().lower() for repo in self.repos.split(",") if repo.strip()]

    def docs_globs_list(self) -> list[str]:
        """Return DOCS_GLOBS split on commas and stripped, blanks dropped; any match counts."""
        return [glob.strip() for glob in self.docs_globs.split(",") if glob.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded on first call."""
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from the environment
