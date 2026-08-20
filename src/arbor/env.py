from __future__ import annotations

import os
from pathlib import Path

from arbor.paths import repo_root


def load_dotenv() -> None:
    env_path = repo_root() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def chat_api_key() -> str:
    load_dotenv()
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def chat_base_url() -> str:
    load_dotenv()
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")


def chat_model() -> str:
    load_dotenv()
    return os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")


def judge_api_key() -> str:
    """Separate judge for RAGAS. Must not be the generator key."""
    load_dotenv()
    judge = os.environ.get("ARBOR_JUDGE_API_KEY") or ""
    generator = chat_api_key()
    if not judge or judge == generator:
        return ""
    return judge
