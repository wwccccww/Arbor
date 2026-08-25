from __future__ import annotations

import hashlib
import hmac


def hash_password(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    expected = hash_password(password)
    return hmac.compare_digest(expected, stored_hash)
