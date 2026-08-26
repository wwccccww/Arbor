"""Inbound HTTP adapters (FastAPI routers). Composition root wires deps; routes live here."""

from arbor.adapters.inbound.http.register_eval import register_eval_routes

__all__ = ["register_eval_routes"]
