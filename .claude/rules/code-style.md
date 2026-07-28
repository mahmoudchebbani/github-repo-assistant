---
paths:
  - "**/*.py"
---

# Code style

Read before writing or modifying Python in `github-repo-assistant`.

This project is written to be read. The bar is not "production-grade enterprise Python" — it is code
that is obviously correct on first reading, by someone who has never seen it before.

## The simplicity contract

**No abstraction with one caller.** This is the rule that shapes everything else.

There is one database, one embedding model, one LLM provider, one repository at a time. There will
never be two. So:

- **No `Protocol`, no ABC, no interface** where a concrete module would do. `search.py` runs SQL
  against Postgres directly.
- **No factories, no registries, no dependency injection.** Import the thing and call it.
- **No nested functions or closures.** Module-level functions; bind arguments with
  `functools.partial` if you genuinely need to.
- **No config classes beyond the single `Settings`.** One object, read through `get_settings()`.
- **No base classes for two things that differ.** Two functions.
- **No premature generality.** A parameter with one possible value is not a parameter.

If you catch yourself writing a layer "so it can be swapped later" — it will not be. Delete the layer.
The day a second implementation genuinely exists is the day to introduce the seam, and not before.

## Shape

- **A module does one nameable thing.** If naming it needs "and", split it.
- **Roughly 100 lines a file, 20 lines a function.** Not a hard limit — a smell. A file at 250 lines
  is doing two jobs.
- **Public functions are typed and carry a one-line docstring** saying what they return, not how.
- **Name after the domain**: `chunk`, `retrieve`, `grade`, `citation` — not `process`, `handle`,
  `manager`, `helper`.
- **Never repeat a literal.** The second occurrence becomes a module constant.
- **No dead code, no commented-out code, no "for future use".** Git remembers; the reader should not
  have to.
- **Comments explain why, never what.** A comment restating the line is noise. A comment explaining a
  non-obvious constant, a silent failure mode, or a decision is worth its space.
- **One line.** A comment that needs a paragraph is a comment that has stopped earning its space —
  say the why in a sentence or delete it. Docstrings are one line too, as above. If the reasoning
  genuinely cannot compress, it is design rationale and belongs in the README, not the source.

## Correctness

- **No API written from memory.** Verify every pgvector, fastembed, LangGraph, dlt, psycopg and
  OpenAI call against the installed package in `.venv/lib/python3.12/site-packages/` or current docs
  before writing it. Cite what you checked in your report.
- **Write the retrieval mechanics; import the plumbing.** Rank fusion, hit-rate and MRR are the
  ideas this project exists to demonstrate — they are short, they are ours, and they are unit-tested.
  Database drivers, ONNX runtimes and markdown parsers are plumbing; use the library.
- **Verify behaviour by running it**, not by reading about it — truncation, rounding, defaults,
  coercion. "The docs say" is not evidence that it did.
- **Fail loud, fail early.** Missing configuration raises at import. A missing API key raises before
  any work is done, never after.
- **Never return a plausible wrong value.** The dangerous bug in a RAG system is the one that returns
  a confident answer from nothing. Before finishing, ask of every change: *what wrong value could a
  caller receive without an exception being raised?* Say the answer out loud, even when it is "none".
  Silence on that question is not an answer.
  - Silent truncation past an embedding model's token window is the specific instance to watch here.
- **Money and scores are `Decimal`, never `float`.** A per-call cost under a hundredth of a cent
  rounds to zero in a coarse numeric type and every later sum is quietly wrong.

## Configuration

- Feature code reads configuration through `get_settings()` only — never `os.environ` directly. Tests
  and scripts may read the environment.
- Secrets have no defaults. `.env.example` is the authoritative template and stays in sync.

## Tooling

Python 3.12 · `uv` with a committed `uv.lock` · `ruff` for lint and format, line length 100.
`make check` runs lint, format check, and tests, and must be green before handing work back.
