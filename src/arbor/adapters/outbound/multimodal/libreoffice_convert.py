from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from arbor.env import libreoffice_path

logger = logging.getLogger("arbor.multimodal.libreoffice")

_LEGACY_OFFICE = {".doc", ".ppt", ".xls", ".odt", ".odp", ".ods"}


def libreoffice_available() -> bool:
    return find_libreoffice() is not None


def find_libreoffice() -> str | None:
    custom = libreoffice_path()
    if custom:
        path = Path(custom).expanduser()
        if path.is_file():
            return str(path)
    for cmd in ("libreoffice", "soffice"):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def is_legacy_office_filename(filename: str) -> bool:
    lower = (filename or "").lower().rsplit("/", 1)[-1]
    if "." not in lower:
        return False
    ext = "." + lower.rsplit(".", 1)[-1]
    return ext in _LEGACY_OFFICE


def convert_office_document(
    data: bytes,
    filename: str,
    *,
    target: str = "docx",
    timeout_sec: int = 120,
) -> bytes | None:
    """Convert legacy Office bytes via headless LibreOffice. Returns None when unavailable."""
    binary = find_libreoffice()
    if not binary:
        return None
    safe_name = (filename or "document").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not safe_name or safe_name.startswith("."):
        safe_name = "document.doc"
    with tempfile.TemporaryDirectory(prefix="arbor-lo-") as tmp:
        work = Path(tmp)
        inp = work / safe_name
        inp.write_bytes(data)
        outdir = work / "out"
        outdir.mkdir()
        cmd = [
            binary,
            "--headless",
            "--convert-to",
            target,
            "--outdir",
            str(outdir),
            str(inp),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("libreoffice convert failed for %s: %s", safe_name, exc)
            return None
        if proc.returncode != 0:
            stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning("libreoffice exit %s for %s: %s", proc.returncode, safe_name, stderr)
            return None
        produced = sorted(outdir.iterdir())
        if not produced:
            return None
        return produced[0].read_bytes()


def convert_legacy_to_modern(data: bytes, filename: str) -> tuple[bytes, str] | None:
    """Try .doc/.ppt → docx/pptx, then plain text fallback."""
    lower = (filename or "").lower().rsplit("/", 1)[-1]
    stem = lower.rsplit(".", 1)[0] if "." in lower else "document"
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext == ".doc":
        converted = convert_office_document(data, filename, target="docx")
        if converted:
            return converted, f"{stem}.docx"
    if ext == ".ppt":
        converted = convert_office_document(data, filename, target="pptx")
        if converted:
            return converted, f"{stem}.pptx"
    converted = convert_office_document(data, filename, target="txt:Text")
    if converted:
        return converted, f"{stem}.txt"
    return None
