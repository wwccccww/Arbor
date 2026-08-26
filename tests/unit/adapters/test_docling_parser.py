from __future__ import annotations

import pytest

from arbor.adapters.outbound.multimodal.docling_parser import docling_available, parse_docling


@pytest.mark.skipif(not docling_available(), reason="docling not installed")
def test_parse_docling_markdown():
    result = parse_docling(b"# Title\n\nBody text here.", "readme.md")
    assert result.parser == "docling"
    assert result.chunks
    assert result.chunks[0].memory_type == "file_chunk"
    assert "Title" in result.chunks[0].text or "Body" in result.chunks[0].text
