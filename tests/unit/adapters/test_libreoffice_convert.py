from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from arbor.adapters.outbound.multimodal.libreoffice_convert import (
    convert_legacy_to_modern,
    convert_office_document,
    is_legacy_office_filename,
    libreoffice_available,
)


def test_is_legacy_office_filename():
    assert is_legacy_office_filename("notes.doc")
    assert not is_legacy_office_filename("notes.docx")


def test_libreoffice_available_when_binary_found():
    with patch(
        "arbor.adapters.outbound.multimodal.libreoffice_convert.find_libreoffice",
        return_value="/usr/bin/libreoffice",
    ):
        assert libreoffice_available()


def test_convert_office_document_reads_produced_file():
    with patch(
        "arbor.adapters.outbound.multimodal.libreoffice_convert.find_libreoffice",
        return_value="/bin/lo",
    ), patch("subprocess.run") as run:
        def fake_run(cmd, capture_output=True, timeout=120, check=False):
            outdir = Path(cmd[cmd.index("--outdir") + 1])
            inp = Path(cmd[-1])
            produced = outdir / f"{inp.stem}.docx"
            produced.write_bytes(b"converted")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        run.side_effect = fake_run
        data = convert_office_document(b"legacy", "notes.doc", target="docx")
    assert data == b"converted"


def test_convert_legacy_to_modern_prefers_docx():
    with patch(
        "arbor.adapters.outbound.multimodal.libreoffice_convert.convert_office_document",
        side_effect=[b"docx-bytes", None],
    ):
        converted = convert_legacy_to_modern(b"legacy", "memo.doc")
    assert converted == (b"docx-bytes", "memo.docx")
