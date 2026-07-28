"""Score dense, lexical and hybrid retrieval on the ground-truth set, and ship the winner."""

from pathlib import Path

import pandas as pd

from assistant.config import RetrievalMode, get_settings
from assistant.search import retrieve
from eval.ground_truth import GROUND_TRUTH_CSV

RESULTS_CSV = Path(__file__).parent / "retrieval_results.csv"
RESULTS_PNG = Path(__file__).parent / "retrieval_results.png"

MODES: tuple[RetrievalMode, ...] = ("dense", "lexical", "hybrid")

_ENV_FILES = (Path(__file__).parent.parent / ".env", Path(__file__).parent.parent / ".env.example")
_MODE_KEY = "RETRIEVAL_MODE"


def hit_rate(results: list[list[str]], expected: list[str]) -> float:
    """Fraction of queries whose expected chunk appears in the retrieved ids."""
    found = sum(
        1 for retrieved, target in zip(results, expected, strict=True) if target in retrieved
    )
    return found / len(expected)


def mean_reciprocal_rank(results: list[list[str]], expected: list[str]) -> float:
    """Mean of 1/rank of the expected chunk, counting 0 when it is absent."""
    total = 0.0
    for retrieved, target in zip(results, expected, strict=True):
        if target in retrieved:
            total += 1.0 / (retrieved.index(target) + 1)
    return total / len(expected)


def retrieved_ids(questions: list[str], mode: RetrievalMode, top_k: int) -> list[list[str]]:
    """Return the ranked chunk ids one mode retrieves for every ground-truth question."""
    # repo=None pools every indexed repo, which is what the app searches unless one is chosen.
    return [[hit.id for hit in retrieve(question, mode, top_k, None)] for question in questions]


def save_chart(scores: pd.DataFrame, top_k: int) -> None:
    """Write the grouped bar chart of both metrics per mode."""
    axes = scores.plot.bar(
        x="mode",
        y=["hit_rate", "mrr"],
        ylim=(0, 1),
        rot=0,
        title=f"Retrieval on 50 questions, k={top_k}",
    )
    axes.figure.savefig(RESULTS_PNG, dpi=150, bbox_inches="tight")


def write_retrieval_mode(path: Path, mode: RetrievalMode) -> None:
    """Rewrite one env file's RETRIEVAL_MODE line in place, leaving every other line untouched."""
    lines = path.read_text().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{_MODE_KEY}="):
            lines[index] = f"{_MODE_KEY}={mode}\n"
            path.write_text("".join(lines))
            return
    raise ValueError(f"{path} has no {_MODE_KEY} line, so the winning mode would not take effect")


def main() -> None:
    """Score every mode on the ground truth, chart it, and write the winner into both env files."""
    # dtype=str: an all-digit chunk id would otherwise be read as an int and match nothing.
    truth = pd.read_csv(GROUND_TRUTH_CSV, dtype=str)
    questions = truth["question"].tolist()
    expected = truth["chunk_id"].tolist()
    top_k = get_settings().top_k
    rows = []
    for mode in MODES:
        results = retrieved_ids(questions, mode, top_k)
        rows.append(
            {
                "mode": mode,
                "hit_rate": round(hit_rate(results, expected), 4),
                "mrr": round(mean_reciprocal_rank(results, expected), 4),
            }
        )
    scores = pd.DataFrame(rows)
    scores.to_csv(RESULTS_CSV, index=False)
    save_chart(scores, top_k)
    print(scores.to_string(index=False))
    # MRR breaks the tie: two modes can both find the chunk while ranking it very differently.
    winner = scores.sort_values(["mrr", "hit_rate"], ascending=False).iloc[0]["mode"]
    for path in _ENV_FILES:
        write_retrieval_mode(path, winner)
    print(f"winner: {winner} - wrote {_MODE_KEY}={winner} to .env and .env.example")


if __name__ == "__main__":
    main()
