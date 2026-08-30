from __future__ import annotations

import base64
import json
import os
import random
from typing import Any

from arbor.env import load_dotenv


def observability_capture_content() -> bool:
    load_dotenv()
    raw = (os.environ.get("OBSERVABILITY_CAPTURE_CONTENT") or "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def observability_capture_sample_rate() -> float:
    load_dotenv()
    raw = (os.environ.get("OBSERVABILITY_CAPTURE_SAMPLE_RATE") or "0.1").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.1
    return max(0.0, min(1.0, value))


def observability_capture_tenants() -> set[str]:
    load_dotenv()
    raw = (os.environ.get("OBSERVABILITY_CAPTURE_TENANTS") or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def should_capture_content(*, tenant_id: str) -> bool:
    if not observability_capture_content():
        return False
    allowed = observability_capture_tenants()
    if allowed and tenant_id not in allowed:
        return False
    rate = observability_capture_sample_rate()
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return random.random() < rate


def encryption_key() -> bytes | None:
    load_dotenv()
    raw = (os.environ.get("OBSERVABILITY_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    try:
        return base64.urlsafe_b64decode(raw.encode("ascii"))
    except Exception:
        return None


def encrypt_payload(payload: dict[str, Any]) -> str | None:
    key = encryption_key()
    if key is None:
        return None
    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(base64.urlsafe_b64encode(key[:32].ljust(32, b"0")[:32]))
        blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return fernet.encrypt(blob).decode("ascii")
    except ImportError:
        return None


def decrypt_payload(token: str) -> dict[str, Any] | None:
    key = encryption_key()
    if key is None:
        return None
    try:
        from cryptography.fernet import Fernet

        fernet = Fernet(base64.urlsafe_b64encode(key[:32].ljust(32, b"0")[:32]))
        raw = fernet.decrypt(token.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None
