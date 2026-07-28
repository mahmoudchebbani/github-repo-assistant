# github-repo-assistant

An agentic RAG assistant that answers questions about a GitHub repository — its issues, pull
requests, comments and markdown docs — and cites the sources it used.

Capstone project for the DataTalksClub **LLM Zoomcamp 2026** cohort. Author: Mahmoud Chebbani.

![Python 3.12](https://img.shields.io/badge/Python%203.12-3776AB?logo=python&logoColor=white)
![PostgreSQL 17 + pgvector](https://img.shields.io/badge/PostgreSQL%2017%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langgraph&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Status](https://img.shields.io/badge/status-complete-brightgreen)

## The problem

A repository's real decision history lives in its issues and pull requests — why something was
rewritten, what broke last time, which approach was rejected and why. None of it is searchable in a
useful way. GitHub search matches keywords, not questions, and the answer is usually spread across a
thread rather than sitting in one comment.

This ingests a repository's own history and answers questions about it in plain language, with
citations back to the issue, PR or file the answer came from.

![A two-turn chat: an answer with an inline citation, a citation link, and a thumbs-up vote](assets/chat-with-citations.jpg)

Every citation in the answer text is also rendered as a link under it, and each turn carries 👍/👎
buttons whose votes are stored and charted.

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

Needs Docker, [uv](https://docs.astral.sh/uv/getting-started/installation/), an OpenAI key, and a
GitHub token with public-repository read access.

```bash
git clone https://github.com/mahmoudchebbani/github-repo-assistant.git
cd github-repo-assistant
uv sync
cp .env.example .env      # then set OPENAI_API_KEY and GITHUB_TOKEN
docker compose up -d --build   # postgres · app · grafana
make ingest               # pull the repositories named in REPOS
make index                # chunk, embed, and index them
```

Then open **http://localhost:8501** and ask a question.

The Grafana dashboard is at **http://localhost:3000/d/assistant**, no login needed. Postgres
publishes `5433` on the host, so this stack does not collide with a local Postgres on 5432.
`make ingest` and `make index` run on the host against that published port, which is why `uv sync`
comes first.

The dashboard is **empty until someone uses the app** — it charts conversations, model calls and
votes, and a fresh install has none of them yet. Ask two or three questions and it fills in.

To edit the application code with live reload, stop the container and run Streamlit on the host —
both bind port 8501, so only one can hold it:

```bash
docker compose stop app
make app                  # http://localhost:8501, reloads on save
```

Other targets: `make check` (lint, format check, tests), `make eval-retrieval`, `make eval-llm`.

## Rubric mapping

| Criterion | Pts | Where it is satisfied |
|---|---|---|
| Problem description | 2 | [The problem](#the-problem) above — a repository's decision history is unsearchable; this answers questions over it |
| Retrieval flow | 2 | a pgvector knowledge base and an OpenAI model, both in the answer path: [`assistant/search.py`](assistant/search.py) + [`assistant/agent.py`](assistant/agent.py) |
| Retrieval evaluation | 2 | [`eval/eval_retrieval.py`](eval/eval_retrieval.py) scores dense vs lexical vs hybrid on hit rate and MRR, **and writes the winner into `.env` and `.env.example`** |
| LLM evaluation | 2 | [`eval/eval_llm.py`](eval/eval_llm.py) judges two answer prompts on groundedness and relevance, **and writes the winner into `.env` and `.env.example`** |
| Interface | 2 | Streamlit chat with history, a repository selector and feedback buttons: [`assistant/app.py`](assistant/app.py) |
| Ingestion pipeline | 2 | dlt, four REST resources into the `raw` schema: [`assistant/ingest.py`](assistant/ingest.py), run by `make ingest` |
| Monitoring | 2 | 👍/👎 votes persisted to the `feedback` table plus a five-panel Grafana dashboard: [`grafana/provisioning/`](grafana/provisioning) |
| Containerization | 2 | postgres · app · grafana in [`docker-compose.yml`](docker-compose.yml), app image in [`Dockerfile`](Dockerfile) |
| Reproducibility | 2 | committed [`uv.lock`](uv.lock), [`.env.example`](.env.example), and the quick start above, re-run from `docker compose down -v` before submission |
| *Best practice* — hybrid search | 1 | pgvector cosine and Postgres full-text search, both legs in [`assistant/search.py`](assistant/search.py). Built and evaluated; **`RETRIEVAL_MODE=dense` ships because the [evaluation](#retrieval--make-eval-retrieval) chose dense**, so set `RETRIEVAL_MODE=hybrid` to run it |
| *Best practice* — re-ranking | 1 | `reciprocal_rank_fusion` in [`assistant/search.py`](assistant/search.py) — written here, not imported. Runs in `hybrid` mode only, for the same reason as the row above |
| *Best practice* — query rewriting | 1 | the `rewrite` node of the agent graph in [`assistant/agent.py`](assistant/agent.py) |
| **Total** | **21** | |

The two evaluations each end by writing their winner into configuration, so the measurement changes
what ships rather than sitting in a notebook. The `app` container reads `.env` at start, so
`docker compose up -d app` is what carries a freshly-evaluated winner into a running stack; a
host-run `make app` picks it up on the next launch.

## Evaluation

Ground truth is 50 questions, generated by asking the model what each of 50 sampled chunks uniquely
answers — sampled evenly across issues, pull requests, comments and docs, so the 1,527 doc chunks do
not decide the outcome. The chunk it came from is the one correct answer.
[`eval/ground_truth.py`](eval/ground_truth.py) writes it and
[`eval/ground_truth.csv`](eval/ground_truth.csv) is committed, because regenerating it would
invalidate every number below.

### Retrieval — `make eval-retrieval`

| mode | hit rate | MRR |
|---|---|---|
| **dense** | **0.78** | **0.5957** |
| lexical | 0.54 | 0.3297 |
| hybrid | 0.74 | 0.5740 |

![Hit rate and MRR per retrieval mode](eval/retrieval_results.png)

**Decision: `RETRIEVAL_MODE=dense`**, written into `.env` and `.env.example` by the script itself.

Hybrid lost. Both legs are real — the lexical leg finds exact identifiers the dense leg blurs, and
the *union* of the two reaches 0.84, above dense alone — but equal-weight Reciprocal Rank Fusion
spends ranks on the weaker leg and gives back more than it gains. See
[Honest limitations](#honest-limitations) for why weighted fusion was not built.

**Hit rate here is chunk-level**: it counts a query as found only when the exact chunk the question
was written from is retrieved. Of dense's 11 misses, 3 returned a *different* chunk of the same
issue, PR or file — the same citation, which a reader would call a hit. Scored per source record
rather than per chunk, dense is 0.84. That number coincides with the union-of-legs 0.84 above by
accident; the two measure unrelated things, and neither is what the table reports.

### Answer prompts — `make eval-llm`

Both prompts answer the same 20 questions from the *same* retrieved context, so the prompt is the
only thing that differs, and an LLM judge scores each answer 1–5 on groundedness and relevance.

| prompt | groundedness | relevance |
|---|---|---|
| **A** — answer concisely, cite every claim | **5.00** ± 0.00 | **5.00** ± 0.00 |
| B — quote the supporting line first, then answer | 4.95 ± 0.05 | 5.00 ± 0.00 |

![Mean groundedness and relevance per answer prompt](eval/llm_results.png)

**Decision: `ANSWER_PROMPT=A`**, written into `.env` and `.env.example` by the script itself. B is
inside its own standard error on groundedness and level on relevance, so the incumbent keeps it.

## Monitoring

![Grafana dashboard: questions per day, latency p50/p95, cumulative cost, feedback ratio, attempts distribution](assets/grafana-dashboard.jpg)

Five panels over the `conversations`, `llm_calls` and `feedback` tables: questions per day, LLM call
latency p50/p95, cumulative cost in USD, the 👍/👎 ratio, and how many retrieval attempts each answer
needed. The datasource and the dashboard are both provisioned from
[`grafana/provisioning/`](grafana/provisioning), so a clean clone gets them with no clicking.

Cost is stored as `NUMERIC(16, 10)` and computed in `Decimal`. The cheapest call in the run above
cost $0.00002025 — a coarser numeric type would round that to zero and every later sum would be
quietly wrong.

The assistant refuses rather than inventing when retrieval comes back with nothing useful, and a
refusal carries no citation links:

![A refusal rendered with no citation links beneath it](assets/refusal.jpg)

## Architecture

```
                             OFFLINE
GitHub REST API ──dlt──▶ Postgres  raw.{issues, pull_requests, comments, docs}
                              │
                        chunk ▼ embed (fastembed BAAI/bge-small-en-v1.5, 384-d)
                     Postgres  public.chunks
                       embedding vector(384)  ── HNSW index
                       lexemes   tsvector     ── GIN index

                             ONLINE
Streamlit chat ──▶ LangGraph   rewrite ─▶ retrieve ─▶ grade ─(weak)─▶ rewrite
                                                        └──(ok)───▶ generate

                     retrieve = dense SQL ─┐
                                           ├─▶ reciprocal_rank_fusion ─▶ top-k
                                lexical SQL ┘
                              │
                Postgres  conversations · llm_calls · feedback ──▶ Grafana
```

**One database, three roles.** dlt's `raw` schema, the `chunks` index and the application's own
tables all live in the same Postgres instance. That is the point of pgvector: no second service to
run, back up, or keep consistent.

**The agent is a loop, not a chain.** `grade` judges whether the retrieved chunks can answer the
query. A weak verdict sends its own complaint back to `rewrite`, which writes a different query and
searches again, up to `MAX_RETRIES` times. `generate` then answers from whatever the last search
found, or refuses when it found nothing.

**Chunking differs by source.** Issue, PR and comment bodies are packed greedily to `CHUNK_CHARS`
with `CHUNK_OVERLAP` carried across the seam, preferring a paragraph boundary. Markdown docs are
first split on their heading structure by `llama-index-core`'s `MarkdownNodeParser`, then each
section is packed the same way — a heading section can itself exceed the model's window.

## Layout

```
assistant/   config · db · ingest · chunk · embed · index · search · prompts · agent · app
eval/        ground truth generation · retrieval evaluation · LLM evaluation
grafana/     provisioned datasource and dashboard
tests/       six test files, one per layer
```

## Honest limitations

Every number below was measured on the shipped corpus, not estimated.

1. **Hybrid lost to dense, and weighted fusion was deliberately not built.** The union of the two
   legs covers 0.84 of the ground truth against dense's 0.78, so a fusion weighting the dense leg
   higher could plausibly beat dense. There is no held-out set — tuning RRF weights on the same 50
   questions the result is reported against is overfitting, and a number produced that way would be
   worth less than the honest 0.74. This is a finding, not an omission.
2. **Retrieval caps nothing per source, so one record can fill the whole context.** Measured over
   the 50 ground-truth questions at `TOP_K=5`: **33 of 50 top-5 sets contain two or more chunks of
   the same source record**, the mean number of distinct sources is **3.52 of 5**, and **7 sets are
   a single source five times over** — issue `#163` accounts for five of those on its own. With
   `CHUNK_OVERLAP=100`, neighbouring chunks are near-duplicates, so a question spanning two issues
   can be answered from one issue restated five ways. The fix is a per-citation cap inside
   `retrieve`, and it is **future work, not a quiet patch**: applying it now would change every
   retrieved set and invalidate all the evaluation results above, which there is no budget to
   re-run. The measurement is the honest deliverable.
3. **The LLM evaluation's metrics saturate.** Both prompts scored 5.00 relevance and effectively
   5.00 groundedness on 20 questions. That evaluation established the two prompts are
   indistinguishable at this sample size; it could not detect a quality regression, because there is
   no headroom left to fall from. A harder question set, or a judge scoring something scarcer than
   groundedness, would be the next thing to build.
4. **The lexical leg is Postgres full-text search, not BM25.** It has no document-length
   normalisation and no IDF saturation, and `to_tsvector('english', …)` mangles code identifiers:
   `retries retrying retry ETIMEDOUT compute_relevance` becomes
   `'comput':5 'etimedout':4 'relev':6 'retri':1,2,3` — three distinct words collapsed into one, an
   identifier split in half, and `ETIMEDOUT` surviving only because it is not an English word. It
   ranks by lexeme overlap, and it is the weaker of the two legs.
5. **HNSW is approximate.** The dense leg reads an index that can miss a true nearest neighbour, so
   the 0.78 hit rate measures the system as shipped rather than exhaustive cosine search.
   Restricting to one repository makes this worse — the index is scanned before the filter — which
   `search_dense` mitigates with `hnsw.iterative_scan = strict_order`.
6. **A refusal phrased entirely in the model's own words is not recognised as a refusal.** Citation
   suppression looks for the mandated refusal sentence as a substring of the answer. Both prompts
   instruct the model to write that sentence verbatim, and it does; but a paraphrase sharing none of
   it slips past the check. Such an answer is then rendered with a link for every source it happens
   to name in brackets — which for a refusal is nothing to cite.
7. **Citations are matched by the literal `[label]` form.** A source the model names any other way —
   parenthesised, or written out in prose — is dropped from the link list. The failure direction is
   therefore under-citing rather than citing something the answer did not use.
8. **`repo=None` searches every repository in the index, not every repository in `REPOS`.** Removing
   a repository from configuration takes it out of the selector but leaves its rows in `chunks`, so
   "All repositories" keeps returning them. Deleting them is a manual `DELETE FROM chunks WHERE repo
   = …`.
9. **Indexing rebuilds rather than diffs.** `make index` deletes and re-embeds every chunk for a
   repository. Ingestion is incremental — dlt merges on primary key and `INGEST_SINCE` bounds the
   pull — but re-embedding is not, so indexing cost grows with corpus size, not with what changed.
   Repositories are also processed one at a time, serially.
10. **A document or issue deleted upstream is never removed.** dlt merges on primary key, so `raw`
    only ever grows; a file dropped from the repository keeps its rows, is re-indexed on every
    `make index`, and stays retrievable behind a citation link that now 404s. Nothing detects it.
    Clearing the repository's rows from `raw` and re-ingesting is the only current cure.
11. **Grafana's latency and cost panels carry a visible "Last 6 hours" override** and do not follow
    the dashboard time picker. Changing the range at the top moves the other three panels only.
12. **Chunk text is truncated at 512 word pieces by the embedding model, silently.** Measured on
    800-character samples: English prose tokenises to 189 pieces, dense code and CJK text both hit
    the 512 cap. fastembed truncates rather than raising, so the tail of such a chunk is stored in
    `chunks.text` but is not represented in its vector — it stays findable by the lexical leg only.
    `CHUNK_CHARS=800` was chosen to keep ordinary prose well inside the window.

## Testing

Six test files, one per layer, run by `make check`. Postgres tests bring up a throwaway
`pgvector/pgvector:pg17` container via `testcontainers`, so the vector and full-text layers run for
real. No test reaches the live GitHub API or OpenAI — the suite passes with no API keys set, but it
does need Docker.

| File | Asserts |
|---|---|
| `test_chunk.py` | packing respects the size budget, consecutive chunks overlap, a markdown doc splits on headings |
| `test_fusion.py` | RRF ranks a document found by both legs above one found by either alone, and is order-stable |
| `test_search.py` | dense finds a paraphrase, lexical finds an exact token and ranks on overlap, a stopword-only question retrieves nothing, and the repo filter holds |
| `test_agent.py` | with an empty index the answer is the refusal and the model is never called, and the configured prompt is the one that generates |
| `test_db.py` | a conversation round-trips, and `cost_usd` comes back as an exact `Decimal` |
| `test_smoke.py` | end to end: a raw record → chunk → embed → index → hybrid retrieval, citation intact |

## Configuration

Every value lives in `.env`, templated by [`.env.example`](.env.example). The two that the
evaluations own — `RETRIEVAL_MODE` and `ANSWER_PROMPT` — are rewritten in place by
`make eval-retrieval` and `make eval-llm`.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Postgres connection string; the `app` container overrides it to reach `postgres:5432` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | generation, grading, ground-truth synthesis and the judge |
| `PRICE_INPUT_PER_1M`, `PRICE_OUTPUT_PER_1M` | USD per million tokens, used to cost every call |
| `GITHUB_TOKEN` | a token with public-repository read access |
| `REPOS` | one or more `owner/repo` slugs, comma-separated |
| `INGEST_SINCE` | how far back to pull issues, PRs and comments |
| `DOCS_GLOBS` | which repository files to ingest as documentation |
| `EMBEDDING_MODEL` | must match the model baked into the app image, or it downloads on first use |
| `CHUNK_CHARS`, `CHUNK_OVERLAP` | the packer's budget and the overlap carried across a seam |
| `RETRIEVAL_MODE` | `dense`, `lexical` or `hybrid` — **set by `make eval-retrieval`** |
| `ANSWER_PROMPT` | `A` or `B` — **set by `make eval-llm`** |
| `TOP_K` | how many chunks reach the answer prompt |
| `MAX_RETRIES` | how many times a weak grade may send the query back to `rewrite` |

Regenerating the ground truth is deliberately not a `make` target — it costs API calls and
invalidates the committed evaluation results. Run `uv run python -m eval.ground_truth` only if you
intend to re-run both evaluations after it.
