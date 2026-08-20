from __future__ import annotations

from typing import Protocol


class ChatPort(Protocol):
    def send_message(self, **kwargs): ...


class EvaluationPort(Protocol):
    def run(self, **kwargs) -> dict: ...
