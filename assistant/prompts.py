"""Every prompt the system uses, as plain strings."""

REFUSAL = "I could not find this in the repository."

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
