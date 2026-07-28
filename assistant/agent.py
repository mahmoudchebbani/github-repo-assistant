"""Answering a question. Replaced by a LangGraph graph in Task 7."""

import time

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from assistant.config import get_settings
from assistant.prompts import ANSWER_A, REFUSAL
from assistant.search import Hit, retrieve


class LLMCall(BaseModel):
    """One model invocation, for the monitoring tables."""

    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class AnswerResult(BaseModel):
    """Everything one answered question produced."""

    text: str
    citations: list[str]
    attempts: int
    calls: list[LLMCall]


def _format_context(hits: list[Hit]) -> str:
    """Join hits into one context block, each line tagged with its citation."""
    return "\n\n".join(f"[{hit.citation}] {hit.text}" for hit in hits)


def answer(question: str) -> AnswerResult:
    """Retrieve context and generate a cited answer."""
    settings = get_settings()
    hits = retrieve(question, settings.retrieval_mode, settings.top_k)
    if not hits:
        return AnswerResult(text=REFUSAL, citations=[], attempts=1, calls=[])

    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    prompt = ANSWER_A.format(question=question, context=_format_context(hits))
    started = time.monotonic()
    response = llm.invoke(prompt)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    usage = response.usage_metadata or {}
    call = LLMCall(
        node="generate",
        model=settings.openai_model,
        prompt_tokens=usage.get("input_tokens", 0),
        completion_tokens=usage.get("output_tokens", 0),
        latency_ms=elapsed_ms,
    )
    return AnswerResult(
        text=str(response.content),
        citations=[hit.citation for hit in hits],
        attempts=1,
        calls=[call],
    )
