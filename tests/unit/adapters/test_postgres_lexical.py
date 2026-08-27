from __future__ import annotations

from arbor.adapters.outbound.postgres.lexical import memory_lexical_tokens
from arbor.application.retrieval_lexical import tokenize


def test_memory_lexical_tokens_joins_cjk_pairs():
    tokens = memory_lexical_tokens("讨厌香菜")
    assert tokens == " ".join(sorted(tokenize("讨厌香菜")))
    assert tokens.strip()
