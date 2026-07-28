"""Sample chunks evenly across the source types and ask the model what each one uniquely answers."""

import csv
from pathlib import Path

from langchain_openai import ChatOpenAI
from psycopg.rows import dict_row
from pydantic import BaseModel

from assistant.config import get_settings
from assistant.db import get_connection

GROUND_TRUTH_CSV = Path(__file__).parent / "ground_truth.csv"

# Sampling each type in turn, rather than at random, stops the 1,527 doc chunks deciding the result.
SOURCE_TYPES = ("issue", "pull_request", "comment", "doc")
SAMPLE_SIZE = 50
# Shorter chunks are "Thanks!" comments, which answer no question and would only add noise.
MIN_CHUNK_CHARS = 200

_FIELDS = ("question", "chunk_id", "repo", "source_type")

_SAMPLE_QUERY = """
    SELECT id, repo, source_type, text
    FROM chunks
    WHERE source_type = %s AND length(text) >= %s
    ORDER BY random()
    LIMIT %s
"""

QUESTION_PROMPT = """Below is one chunk of text taken from a GitHub repository.

Write the single question a user of that repository would ask, which this chunk answers.

Rules:
- The question must be answerable from this chunk alone.
- Write it as someone who has never seen the chunk would ask it: no issue or pull request numbers,
  no file, script or path names, no URLs, and none of the chunk's own title.
- Never point back at the chunk, with "this" or with "the": not "this issue", not "in the pull
  request", not "the comment", not "the text above". The question is read entirely on its own.
- Name the subject it asks about, so nothing outside the question is needed to understand it.
- Do not quote or restate the chunk's wording; ask about what it says.
- Be specific enough that an unrelated chunk would not answer it equally well.
- One sentence, plain English.

Source type: {source_type}

Chunk:
{text}
"""


class GeneratedQuestion(BaseModel):
    """The single question the model writes for one chunk."""

    question: str


def sample_chunks() -> list[dict[str, str]]:
    """Return up to SAMPLE_SIZE substantial chunks, split as evenly as the source types allow."""
    base, remainder = divmod(SAMPLE_SIZE, len(SOURCE_TYPES))
    sampled: list[dict[str, str]] = []
    with get_connection() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        for index, source_type in enumerate(SOURCE_TYPES):
            quota = base + (1 if index < remainder else 0)
            rows = cursor.execute(_SAMPLE_QUERY, (source_type, MIN_CHUNK_CHARS, quota)).fetchall()
            # A stratum too small for its quota shrinks the sample rather than failing it, loudly.
            print(f"{source_type}: sampled {len(rows)} of {quota}")
            sampled.extend(rows)
    return sampled


def main() -> None:
    """Write one generated question per sampled chunk to eval/ground_truth.csv."""
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model, api_key=settings.openai_api_key
    ).with_structured_output(GeneratedQuestion)
    chunks = sample_chunks()
    with GROUND_TRUTH_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDS)
        writer.writeheader()
        for chunk in chunks:
            prompt = QUESTION_PROMPT.format(source_type=chunk["source_type"], text=chunk["text"])
            generated = model.invoke(prompt)
            assert isinstance(generated, GeneratedQuestion)  # the schema this client was built with
            writer.writerow(
                {
                    "question": generated.question,
                    "chunk_id": chunk["id"],
                    "repo": chunk["repo"],
                    "source_type": chunk["source_type"],
                }
            )
    print(f"wrote {len(chunks)} questions to {GROUND_TRUTH_CSV}")


if __name__ == "__main__":
    main()
