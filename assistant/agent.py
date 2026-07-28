"""The agent graph: rewrite, retrieve, grade, then answer from the chunks or refuse."""

import time
from functools import lru_cache
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from assistant.config import get_settings
from assistant.prompts import (
    ANSWER_A,
    FEEDBACK,
    GRADE,
    GRADE_YES,
    HISTORY,
    HISTORY_TURN,
    REFUSAL,
    REWRITE,
)
from assistant.search import Hit, retrieve

# One past exchange: what the user asked, and what the assistant answered.
Turn = tuple[str, str]

# Node names reach Grafana through llm_calls.node, so the graph and _invoke must spell them once.
REWRITE_NODE = "rewrite"
RETRIEVE_NODE = "retrieve"
GRADE_NODE = "grade"
GENERATE_NODE = "generate"

# Only the newest turns can still be referred to, and this keeps a long chat off the rewrite prompt.
HISTORY_TURNS = 3

# Measured on this graph: rewrite, retrieve and grade per attempt, then generate and a closing tick.
SUPERSTEPS_PER_ATTEMPT = 3
SUPERSTEPS_TO_FINISH = 2


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


class State(TypedDict):
    """What flows between the nodes; every node returns the whole thing."""

    question: str
    history: list[Turn]
    repo: str | None
    query: str
    feedback: str
    hits: list[Hit]
    strong: bool
    attempts: int
    answer: str
    calls: list[LLMCall]


@lru_cache
def _model() -> ChatOpenAI:
    """Return the process-wide chat client, built on first use so importing needs no key."""
    settings = get_settings()
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def _invoke(node: str, prompt: str) -> tuple[str, LLMCall]:
    """Call the model once and record what it cost; the only network edge in the graph."""
    settings = get_settings()
    started = time.monotonic()
    response = _model().invoke(prompt)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    usage = response.usage_metadata or {}
    call = LLMCall(
        node=node,
        model=settings.openai_model,
        prompt_tokens=usage.get("input_tokens", 0),
        completion_tokens=usage.get("output_tokens", 0),
        latency_ms=elapsed_ms,
    )
    return str(response.content), call


def _format_context(hits: list[Hit]) -> str:
    """Join hits into one context block, each line tagged with its citation."""
    return "\n\n".join(f"[{hit.citation}] {hit.text}" for hit in hits)


def _format_history(history: list[Turn]) -> str:
    """Render the last few turns for the rewrite prompt, or nothing on a first question."""
    if not history:
        return ""
    turns = [HISTORY_TURN.format(question=q, answer=a) for q, a in history[-HISTORY_TURNS:]]
    return HISTORY.format(turns="\n".join(turns))


def _format_feedback(query: str, reason: str) -> str:
    """Render the grader's complaint about the last query, or nothing on a first attempt."""
    return FEEDBACK.format(query=query, reason=reason) if reason else ""


def rewrite(state: State) -> State:
    """Turn the question into a standalone search query, resolving what earlier turns implied."""
    if not state["history"] and state["attempts"] == 0:
        # Nothing refers back and nothing has been searched, so the user's own words are the query.
        return {**state, "query": state["question"]}
    prompt = REWRITE.format(
        question=state["question"],
        history=_format_history(state["history"]),
        feedback=_format_feedback(state["query"], state["feedback"]),
    )
    query, call = _invoke(REWRITE_NODE, prompt)
    # An empty rewrite would embed to noise and match no lexemes, so fall back to the question.
    return {**state, "query": query.strip() or state["question"], "calls": [*state["calls"], call]}


def retrieve_node(state: State) -> State:
    """Search the index with the current query and count the attempt."""
    settings = get_settings()
    hits = retrieve(state["query"], settings.retrieval_mode, settings.top_k, state["repo"])
    return {**state, "hits": hits, "attempts": state["attempts"] + 1}


def grade(state: State) -> State:
    """Judge whether the chunks can answer the query; nothing retrieved is weak for free."""
    if not state["hits"]:
        return {**state, "strong": False}
    # The query, not the question: a verdict on different wording is a verdict on another search.
    prompt = GRADE.format(question=state["query"], context=_format_context(state["hits"]))
    verdict, call = _invoke(GRADE_NODE, prompt)
    return {
        **state,
        "strong": verdict.strip().upper().startswith(GRADE_YES),
        "feedback": verdict.strip(),
        "calls": [*state["calls"], call],
    }


def generate(state: State) -> State:
    """Write the cited answer from the chunks, or refuse outright when there are none."""
    if not state["hits"]:
        # A generation call with no context can only invent or refuse, so refuse without paying.
        return {**state, "answer": REFUSAL}
    # The query, not the question: a follow-up's pronoun has no referent without prior answer text.
    prompt = ANSWER_A.format(question=state["query"], context=_format_context(state["hits"]))
    text, call = _invoke(GENERATE_NODE, prompt)
    return {**state, "answer": text, "calls": [*state["calls"], call]}


def should_retry(state: State) -> str:
    """Re-search only when a search returned something weak and the retry budget still allows it."""
    # Dense and hybrid return rows for any wording, so no hits means an empty scope, not a bad ask.
    if not state["hits"] or state["strong"]:
        return GENERATE_NODE
    # attempts counts retrievals, so the first one is not a retry.
    if state["attempts"] > get_settings().max_retries:
        return GENERATE_NODE
    return REWRITE_NODE


_builder = StateGraph(State)
_builder.add_node(REWRITE_NODE, rewrite)
_builder.add_node(RETRIEVE_NODE, retrieve_node)
_builder.add_node(GRADE_NODE, grade)
_builder.add_node(GENERATE_NODE, generate)
_builder.add_edge(START, REWRITE_NODE)
_builder.add_edge(REWRITE_NODE, RETRIEVE_NODE)
_builder.add_edge(RETRIEVE_NODE, GRADE_NODE)
_builder.add_conditional_edges(GRADE_NODE, should_retry, [REWRITE_NODE, GENERATE_NODE])
_builder.add_edge(GENERATE_NODE, END)
GRAPH = _builder.compile()


def answer(
    question: str, repo: str | None = None, history: list[Turn] | None = None
) -> AnswerResult:
    """Answer a question from the index; repo=None searches every repo, history is oldest first."""
    settings = get_settings()
    start: State = {
        "question": question,
        "history": history or [],
        "repo": repo,
        "query": question,
        "feedback": "",
        "hits": [],
        "strong": False,
        "attempts": 0,
        "answer": "",
        "calls": [],
    }
    # Without a limit a mis-wired loop would run LangGraph's default 10007 steps, billing for each.
    limit = SUPERSTEPS_PER_ATTEMPT * (settings.max_retries + 1) + SUPERSTEPS_TO_FINISH
    final = GRAPH.invoke(start, {"recursion_limit": limit})
    text = final["answer"]
    # A refusal cites nothing; otherwise list retrieved sources once each, in retrieval order.
    retrieved = dict.fromkeys(hit.citation for hit in final["hits"])
    # Substring, not equality: an exhausted loop generates from rejected context, so it paraphrases.
    citations = [] if REFUSAL in text else list(retrieved)
    return AnswerResult(
        text=text, citations=citations, attempts=final["attempts"], calls=final["calls"]
    )
