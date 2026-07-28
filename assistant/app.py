"""Streamlit interface. Becomes a chat with feedback in Task 8."""

import streamlit as st

from assistant.agent import answer
from assistant.config import get_settings

ALL_REPOS = "All repositories"

st.title("github-repo-assistant")

choice = st.selectbox("Repository", [ALL_REPOS, *get_settings().repo_list()])
question = st.text_input("Ask about the repository")
if question:
    repo = None if choice == ALL_REPOS else choice
    result = answer(question, repo)
    st.write(result.text)
    st.caption(" · ".join(result.citations))
