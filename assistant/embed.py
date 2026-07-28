"""The single embedding model, shared by indexing and querying."""

from functools import lru_cache

from fastembed import TextEmbedding

from assistant.config import get_settings


@lru_cache
def _model() -> TextEmbedding:
    """Load the ONNX model once, on first use rather than at import."""
    return TextEmbedding(model_name=get_settings().embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of documents."""
    return [vector.tolist() for vector in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    """Embed a single query with the same model as the corpus."""
    # No bge query instruction: fastembed applies none; retrieval eval measures whether it matters.
    return embed_texts([text])[0]
