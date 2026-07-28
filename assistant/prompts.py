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

ANSWER_B = f"""You answer questions about a GitHub repository using only the context below.

Work in this order:
1. Quote the line from the context that answers the question, putting that block's citation in
   square brackets before the quote. Quote at most three such lines.
2. Then state the answer in one or two sentences, using nothing beyond what you quoted.

If no line in the context answers the question, skip both steps and write exactly this, alone:
"{REFUSAL}"

Question: {{question}}

Context:
{{context}}
"""

# ANSWER_PROMPT selects one; eval/eval_llm.py scores both and writes the winner back into .env.
ANSWER_PROMPTS = {"A": ANSWER_A, "B": ANSWER_B}

JUDGE = """Grade one answer that a retrieval system gave about a GitHub repository.

Score each of these from 1 to 5:
- groundedness: 5 when every claim is supported by the context, 1 when the answer states things the
  context does not say.
- relevance: 5 when it answers the question that was asked, 1 when it answers a different one.

An answer that says the context does not contain the answer, and is right about that, scores 5 on
both. Grade only what the answer claims, never its length, its wording or its formatting.

Question: {question}

Context:
{context}

Answer:
{answer}
"""
