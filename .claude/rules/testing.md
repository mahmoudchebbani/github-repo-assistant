---
paths:
  - "tests/**/*.py"
  - "**/conftest.py"
---

# Testing

Read before writing or running tests in `github-repo-assistant`.

**The suite is deliberately small — six tests, one per layer.** This project's quality evidence is its
offline evaluation scripts under `eval/`, not a coverage number. A large suite here would cost more
than it protects.

## The six

Do not grow past these without being asked:

| File | Asserts |
|---|---|
| `test_chunk.py` | packing respects the size budget, consecutive chunks overlap, and a markdown doc splits on its headings |
| `test_fusion.py` | RRF ranks a document found by both legs above one found by either alone, and is order-stable |
| `test_search.py` | all three modes return results, and the lexical leg finds an exact string the dense leg misses |
| `test_agent.py` | with an empty index the answer is the refusal, not an invention |
| `test_db.py` | a conversation round-trips, and `cost_usd` comes back as an exact `Decimal` |
| `test_smoke.py` | end to end: fixture rows → index → ask → an answer carrying a citation |

## What earns a test here

- **A pure function with a real invariant** — chunk packing, fusion ordering, citation format.
- **A refusal path.** The most valuable single test in a RAG system is the one proving it says "I
  don't know" instead of inventing. It is the failure that costs the most and shows the least.
- **A round-trip through a real store**, so type coercion is exercised rather than assumed.

## What does not

- Getters, constructors, dataclass field access.
- Anything asserting an implementation detail rather than a behaviour. If the test breaks when the
  code moves but the behaviour does not, it is a liability.
- Prompt wording, model output text, or anything else non-deterministic. The evaluation scripts
  measure answer quality; tests do not.

## How

- **Mock only the network edge.** GitHub responses are recorded fixtures. Nothing we wrote ourselves
  is ever mocked — a test that mocks our own function tests the mock.
- **Postgres tests use a throwaway `pgvector/pgvector:pg17` container** via `testcontainers`, never a
  development database. The vector and full-text layers then run for real, with nothing faked — which
  matters, because their behaviour (HNSW recall, English stemming) is the thing most likely to
  surprise.
- **`test_fusion.py` is pure** — no database, no network. RRF is the cheapest thing in the project to
  prove correct, so prove it.
- **Test names are sentences.** `test_an_empty_index_produces_a_refusal`, not `test_agent_2`.
- **Watch a new test fail before making it pass**, and check it fails for the reason you expect. A
  test that has never been red has proven nothing.
- **No test reaches the live GitHub API or OpenAI.** The suite must pass with no API keys set. Docker
  is required, because Postgres is real; network credentials are not.
- **The OpenAI client is the network edge, so stubbing it is allowed** — that is how `test_agent.py`
  runs offline. Stubbing anything we wrote is not.
