from __future__ import annotations

from dataclasses import dataclass

from arbor.domain.shared.ids import UserId


@dataclass
class User:
    id: UserId
    email: str
