from __future__ import annotations

from arbor.application.retrieval_lexical import tokenize


def memory_lexical_tokens(text: str) -> str:
    """Space-joined lexical tokens for Postgres tsvector indexing."""
    tokens = sorted(tokenize(text or ""))
    return " ".join(tokens) if tokens else ""
