# CLAUDE.md

Guidance for Claude Code when working in `github-repo-assistant`.

## What this is

An agentic RAG assistant over a GitHub repository's issues, pull requests, comments and markdown
docs. See [`README.md`](README.md) for what it does, the architecture, and how to run it.

## The one rule that outranks the others

**The code must be simple enough that a reader understands any file without opening a second one.**

Great code, simple code, not clever code. When two designs both work, ship the one that needs less
explaining.

The specific consequences are in [`.claude/rules/code-style.md`](.claude/rules/code-style.md). The
headline: **no abstraction with one caller.** No protocols, no ABCs, no factories, no dependency
injection, no nested functions. This project has exactly one database, one embedder, one LLM
provider, and it will never have two.

The corollary that is easy to miss: **write the retrieval mechanics rather than importing them.**
Reciprocal Rank Fusion is fifteen lines here on purpose. A library call that hides rank fusion behind
a parameter shows the docs were read; an implementation shows the concept is understood.

## How work gets done

- **Vertical slice first.** Get a complete, ugly path working end to end, then thicken each layer in
  place. Never leave the project in a state where nothing answers a question.
- **Tests are light by design.** Six, one per layer, listed in
  [`.claude/rules/testing.md`](.claude/rules/testing.md). Do not grow the suite beyond that without
  being asked. The evaluation scripts under `eval/` are the real quality evidence.
- **No API written from memory.** Every pgvector, fastembed, LangGraph, dlt and psycopg call is
  checked against the installed package or current documentation before use. That matters most for
  LangGraph, the one library here with no prior line written.
- **Verify behaviour by running it**, not by reading about it. Truncation, stemming, rounding and
  defaults are established by execution.
- **Commit each task when it is done and green.** One logical change per commit, message a concise
  imperative summary (`feat:`, `test:`, `chore:`, `docs:`). Never push, and never create or switch
  branches. Publishing is the developer's call.

## Definition of done

1. `make check` passes. That is ruff lint, ruff format check and pytest. Paste the output, do not
   summarise it.
2. The change is visible working in the app, or its script was run and its output shown.
3. Public functions are typed and have a one-line docstring.
4. The `code-reviewer` agent has run over the diff at the end of a slice, not after every edit, and
   its findings are fixed or explicitly justified.

## Rules and agents

Path-scoped rules in `.claude/rules/` load automatically for matching files:

- [`code-style.md`](.claude/rules/code-style.md) covers `**/*.py`. The simplicity contract.
- [`testing.md`](.claude/rules/testing.md) covers `tests/**`. What earns a test, and what does not.

Two agents in `.claude/agents/`:

- `implementer` builds a task, verifies it, commits, reports.
- `code-reviewer` is read-only. It reviews correctness first and clarity second, and treats
  unnecessary abstraction as a defect in this project.

Auto-loading is not guaranteed to reach a subagent. Any brief given to an agent must name the rules
it needs to follow.
