"""Streamlit interface. Becomes a chat with feedback in Task 8."""

import streamlit as st

from assistant.agent import answer

st.title("github-repo-assistant")

question = st.text_input("Ask about the repository")
if question:
    result = answer(question)
    st.write(result.text)
    st.caption(" · ".join(result.citations))
