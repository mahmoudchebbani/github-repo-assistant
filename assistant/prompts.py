"""Every prompt the system uses, as plain strings."""

REFUSAL = "I could not find this in the repository."

REWRITE = """Rewrite this question as a search query for a GitHub repository's
issues, pull requests and documentation. Resolve anything the question refers to
from the conversation below, so the query stands alone. Use plain keywords only,
with no search operators and no quotes. Return only the query.
{history}
Question: {question}
{feedback}
"""

HISTORY = """
Conversation so far, oldest first:
{turns}
"""

HISTORY_TURN = """Q: {question}
A: {answer}"""

FEEDBACK = """The last search used the query "{query}" and the grader rejected it: {reason}
Write a different query."""

GRADE_YES = "YES"

GRADE = f"""Can the context below answer the question? Reply with exactly one word,
{GRADE_YES} or NO, then a colon and a short reason.

Question: {{question}}

Context:
{{context}}
"""

ANSWER_A = f"""You answer questions about a GitHub repository using only the context below.

Rules:
- Use only the context. If it does not contain the answer, say exactly:
  "{REFUSAL}"
- Cite every claim with the citation given for that context block, in square brackets.
- Be concise.

Question: {{question}}

Context:
{{context}}
"""
