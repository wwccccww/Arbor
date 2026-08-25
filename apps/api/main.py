"""FastAPI application factory."""

from apps.api.factory import create_app, create_app_from_env
from arbor.adapters.outbound.embedding import embedding_client_from_env

__all__ = ["create_app", "create_app_from_env", "embedding_client_from_env"]
