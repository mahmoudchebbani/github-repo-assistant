"""Streamlit chat over the indexed repositories, recording every turn, call and vote."""

from uuid import UUID

import psycopg
import streamlit as st

from assistant.agent import AnswerResult, answer
from assistant.config import get_settings
from assistant.db import (
    cost_usd,
    get_connection,
    init_db,
    save_conversation,
    save_feedback,
    save_llm_call,
)

ALL_REPOS = "All repositories"
# st.feedback("thumbs") reports 0 for the down thumb and 1 for the up one; feedback.vote stores ±1.
VOTES = {0: -1, 1: 1}


@st.cache_resource
def connection() -> psycopg.Connection:
    """Return the one long-lived connection; this script reruns on every click, connecting costs."""
    # Before get_connection, which needs the vector type: opening the app first must not error.
    with psycopg.connect(get_settings().database_url) as bootstrap:
        init_db(bootstrap)
    conn = get_connection()
    # Autocommit because every session shares this one: a failed write must not abort theirs too.
    conn.autocommit = True
    return conn


def save_turn(repo: str | None, question: str, result: AnswerResult) -> UUID:
    """Store one answered turn with everything it spent, and return the conversation id."""
    conn = connection()
    conversation_id = save_conversation(
        conn, repo, question, result.text, get_settings().retrieval_mode, result.attempts
    )
    for call in result.calls:
        save_llm_call(
            conn,
            conversation_id,
            call.node,
            call.model,
            call.prompt_tokens,
            call.completion_tokens,
            cost_usd(call.prompt_tokens, call.completion_tokens),
            call.latency_ms,
        )
    return conversation_id


def record_vote(conversation_id: UUID) -> None:
    """Store or clear this turn's vote; Streamlit calls this when that turn's thumbs change."""
    thumb = st.session_state[str(conversation_id)]
    # Clicking the selected thumb again clears it, and a retraction must leave nothing behind.
    save_feedback(connection(), conversation_id, None if thumb is None else VOTES[thumb])


st.title("github-repo-assistant")
st.caption("Ask about the issues, pull requests and docs of an indexed repository.")

choice = st.selectbox("Repository", [ALL_REPOS, *get_settings().repo_list()])
# A transcript per repository, so switching does not answer a follow-up from the one just left.
transcripts = st.session_state.setdefault("transcripts", {})
# One entry per answered turn: the question asked, what came back, and the row it was written to.
exchanges = transcripts.setdefault(choice, [])

question = st.chat_input("Ask about the repository")
if question:
    repo = None if choice == ALL_REPOS else choice
    with st.spinner("Searching the repository…"):
        result = answer(question, repo, [(asked, past.text) for asked, past, _ in exchanges])
    exchanges.append((question, result, save_turn(repo, question, result)))

for asked, result, conversation_id in exchanges:
    st.chat_message("user").write(asked)
    with st.chat_message("assistant"):
        st.markdown(result.text)
        if result.citations:
            st.caption(" · ".join(f"[{c.label}]({c.url})" for c in result.citations))
        st.feedback(
            "thumbs",
            key=str(conversation_id),
            on_change=record_vote,
            args=(conversation_id,),
        )
