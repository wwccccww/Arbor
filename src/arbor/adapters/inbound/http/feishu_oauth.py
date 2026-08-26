from __future__ import annotations

import base64
import json

from arbor.domain.shared.ids import TenantId, UserId


def encode_oauth_state(tenant_id: TenantId, user_id: UserId) -> str:
    payload = json.dumps({"t": tenant_id.value, "u": user_id.value}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_oauth_state(state: str) -> tuple[TenantId, UserId]:
    padded = state + "=" * (-len(state) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    return TenantId(str(data["t"])), UserId(str(data["u"]))
