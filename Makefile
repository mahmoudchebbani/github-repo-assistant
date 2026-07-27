.PHONY: up down check lint fmt test ingest index app eval-retrieval eval-llm

up:            ; docker compose up -d
down:          ; docker compose down
lint:          ; uv run ruff check .
fmt:           ; uv run ruff format .
test:          ; uv run pytest -q
check:         ; uv run ruff check . && uv run ruff format --check . && uv run pytest -q
ingest:        ; uv run python -m assistant.ingest
index:         ; uv run python -m assistant.index
app:           ; uv run streamlit run assistant/app.py
eval-retrieval:; uv run python -m eval.eval_retrieval
eval-llm:      ; uv run python -m eval.eval_llm
