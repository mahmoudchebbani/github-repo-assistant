"""Judge both answer prompts on one shared retrieved context per question, and ship the winner."""

from decimal import Decimal
from pathlib import Path

import pandas as pd
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from assistant.agent import GENERATE_NODE, _format_context, _invoke
from assistant.config import get_settings
from assistant.db import cost_usd
from assistant.prompts import ANSWER_PROMPTS, JUDGE
from assistant.search import retrieve
from eval.env_file import ENV_FILES, write_setting
from eval.ground_truth import GROUND_TRUTH_CSV, SOURCE_TYPES

RESULTS_CSV = Path(__file__).parent / "llm_results.csv"
RESULTS_PNG = Path(__file__).parent / "llm_results.png"

# Five per source type: the ground truth is grouped by type, so head(20) would be issues and PRs.
PER_SOURCE_TYPE = 5
SAMPLE_SIZE = PER_SOURCE_TYPE * len(SOURCE_TYPES)

METRICS = ("groundedness", "relevance")
_PROMPT_KEY = "ANSWER_PROMPT"


class Scores(BaseModel):
    """The judge's two 1-5 scores for one answer."""

    groundedness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)


def judge(model: Runnable, question: str, context: str, answer: str) -> tuple[Scores, Decimal]:
    """Score one answer against the context it was written from, and price the judging call."""
    result = model.invoke(JUDGE.format(question=question, context=context, answer=answer))
    scores, usage = result["parsed"], result["raw"].usage_metadata
    # include_raw returns a parsing failure rather than raising, and None here would score nothing.
    if scores is None or usage is None:
        raise RuntimeError(f"the judge returned no usable scores: {result['parsing_error']}")
    return scores, cost_usd(usage["input_tokens"], usage["output_tokens"])


def paired_difference(scored: pd.DataFrame, metric: str) -> pd.Series:
    """Return B minus A on one metric question by question, so the pairing is not thrown away."""
    paired = scored.pivot(index="question", columns="prompt", values=metric)
    return paired["B"] - paired["A"]


def winner(scored: pd.DataFrame) -> str:
    """Return the prompt to ship: B needs a real groundedness gain and no real relevance loss."""
    grounded = paired_difference(scored, "groundedness")
    relevant = paired_difference(scored, "relevance")
    # A gap inside its own standard error is noise at this sample size, so incumbent A keeps it.
    return "B" if grounded.mean() > grounded.sem() and relevant.mean() >= -relevant.sem() else "A"


def summarise(scored: pd.DataFrame) -> pd.DataFrame:
    """Return each prompt's mean score per metric with the standard error of that mean beside it."""
    return (
        scored.groupby("prompt")
        .agg(
            groundedness=("groundedness", "mean"),
            groundedness_se=("groundedness", "sem"),
            relevance=("relevance", "mean"),
            relevance_se=("relevance", "sem"),
        )
        .round(4)
        .reset_index()
    )


def save_chart(summary: pd.DataFrame) -> None:
    """Write the grouped bar chart of both mean scores per prompt, with standard error bars."""
    axes = summary.plot.bar(
        x="prompt",
        y=list(METRICS),
        yerr=summary[["groundedness_se", "relevance_se"]].T.to_numpy(),
        ylim=(0, 5),
        rot=0,
        title=f"Answer prompts judged on {SAMPLE_SIZE} questions",
    )
    # Both bars reach the top of a 1-5 axis, so an in-axes legend would sit on the data.
    axes.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    axes.figure.savefig(RESULTS_PNG, dpi=150, bbox_inches="tight")


def main() -> None:
    """Judge both prompts on one shared context per question, chart it, and ship the winner."""
    settings = get_settings()
    # dtype=str: an all-digit chunk id would otherwise be read as an int and match nothing.
    truth = pd.read_csv(GROUND_TRUTH_CSV, dtype=str)
    sample = truth.groupby("source_type", sort=False).head(PER_SOURCE_TYPE)
    model = ChatOpenAI(
        model=settings.openai_model, api_key=settings.openai_api_key
    ).with_structured_output(Scores, include_raw=True)
    spend = Decimal(0)
    rows = []
    for question in sample["question"]:
        # One retrieval shared by both prompts, so the prompt is the only thing that differs.
        hits = retrieve(question, settings.retrieval_mode, settings.top_k, None)
        context = _format_context(hits)
        for name, template in ANSWER_PROMPTS.items():
            text, call = _invoke(GENERATE_NODE, template.format(question=question, context=context))
            scores, judged = judge(model, question, context, text)
            spend += cost_usd(call.prompt_tokens, call.completion_tokens) + judged
            rows.append({"question": question, "prompt": name, **scores.model_dump()})
    scored = pd.DataFrame(rows)
    summary = summarise(scored)
    summary.to_csv(RESULTS_CSV, index=False)
    save_chart(summary)
    print(summary.to_string(index=False))
    for metric in METRICS:
        difference = paired_difference(scored, metric)
        print(f"{metric}: B - A = {difference.mean():+.4f} (standard error {difference.sem():.4f})")
    print(f"spend for this run: ${spend:.4f}")
    shipped = winner(scored)
    for path in ENV_FILES:
        write_setting(path, _PROMPT_KEY, shipped)
    print(f"winner: {shipped} - wrote {_PROMPT_KEY}={shipped} to .env and .env.example")


if __name__ == "__main__":
    main()
