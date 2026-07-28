# github-repo-assistant

An agentic RAG assistant that answers questions about a GitHub repository — its issues, pull
requests, comments and markdown docs — and cites the sources it used.

Capstone project for the DataTalksClub **LLM Zoomcamp 2026** cohort. Author: Mahmoud Chebbani.

![Python 3.12](https://img.shields.io/badge/Python%203.12-3776AB?logo=python&logoColor=white)
![PostgreSQL 17 + pgvector](https://img.shields.io/badge/PostgreSQL%2017%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langgraph&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Status](https://img.shields.io/badge/status-in%20progress-orange)

## The problem

A repository's real decision history lives in its issues and pull requests — why something was
rewritten, what broke last time, which approach was rejected and why. None of it is searchable in a
useful way. GitHub search matches keywords, not questions, and the answer is usually spread across a
thread rather than sitting in one comment.

This ingests a repository's own history and answers questions about it in plain language, with
citations back to the issue, PR or file the answer came from.

## How it works

```
OFFLINE   GitHub API ──dlt──▶ Postgres raw ──chunk+embed──▶ chunks (vector + tsvector)

ONLINE    Streamlit ──▶ LangGraph  rewrite ▶ retrieve ▶ grade ─(weak)─▶ rewrite
                                                        └─(ok)──▶ cited answer
          retrieve = pgvector cosine + Postgres full-text, fused with Reciprocal Rank Fusion
```

Everything runs in Postgres — raw data, embeddings and application state in one database. OpenAI is
the only external dependency.

## Quick start

Needs Docker, [uv](https://docs.astral.sh/uv/getting-started/installation/), and an OpenAI key.

```bash
git clone https://github.com/mahmoudchebbani/github-repo-assistant.git
cd github-repo-assistant
uv sync
cp .env.example .env      # then set OPENAI_API_KEY and GITHUB_TOKEN
docker compose up -d
make ingest               # pull the repositories named in REPOS
make index                # chunk, embed, and index it
make app                  # http://localhost:8501
```

Grafana is on `http://localhost:3000`, no login needed. Postgres binds `5433`.

## Layout

```
assistant/   config · db · ingest · chunk · embed · index · search · prompts · agent · app
eval/        ground truth generation · retrieval evaluation · LLM evaluation
grafana/     provisioned datasource and dashboard
tests/       six tests, one per layer
```

## Status

Build in progress. Evaluation results and screenshots land with the finished application.
