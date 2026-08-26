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


def reasoner_model() -> str:
    load_dotenv()
    return os.environ.get("DEEPSEEK_REASONER_MODEL") or os.environ.get("DEEPSEEK_CHAT_MODEL") or "deepseek-reasoner"


def judge_api_key() -> str:
    """Separate judge for RAGAS. Must not be the generator key."""
    load_dotenv()
    judge = os.environ.get("ARBOR_JUDGE_API_KEY") or ""
    generator = chat_api_key()
    if not judge or judge == generator:
        return ""
    return judge


def database_url() -> str:
    load_dotenv()
    return os.environ.get("DATABASE_URL") or ""


def data_dir() -> Path:
    load_dotenv()
    raw = os.environ.get("ARBOR_DATA_DIR") or ""
    if raw:
        return Path(raw).expanduser()
    return repo_root() / ".arbor-data"


def embedding_api_key() -> str:
    load_dotenv()
    return os.environ.get("EMBEDDING_API_KEY") or os.environ.get("SILICONFLOW_API_KEY") or ""


def embedding_base_url() -> str:
    load_dotenv()
    return (
        os.environ.get("EMBEDDING_BASE_URL")
        or os.environ.get("SILICONFLOW_BASE_URL")
        or "https://api.siliconflow.cn/v1"
    ).rstrip("/")


def embedding_model() -> str:
    load_dotenv()
    return os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")


def redis_url() -> str:
    load_dotenv()
    return os.environ.get("REDIS_URL") or os.environ.get("ARBOR_REDIS_URL") or ""


def job_queue_backend() -> str:
    """sync (inline) or redis (ARQ). Default: redis when REDIS_URL set, else sync."""
    load_dotenv()
    explicit = (os.environ.get("ARBOR_JOB_QUEUE") or "").strip().lower()
    if explicit in {"sync", "redis"}:
        return explicit
    return "redis" if redis_url() else "sync"


def object_store_backend() -> str:
    load_dotenv()
    raw = (os.environ.get("ARBOR_OBJECT_STORE") or "local").strip().lower()
    if raw in {"local", "postgres", "s3"}:
        return raw
    return "local"


def demo_tokens_disabled() -> bool:
    load_dotenv()
    raw = (os.environ.get("ARBOR_DISABLE_DEMO_TOKENS") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def strict_tenant_membership() -> bool:
    """When set, bearer tokens must belong to X-Tenant-Id membership (no cross-tenant owner bypass)."""
    load_dotenv()
    raw = (os.environ.get("ARBOR_STRICT_TENANT_MEMBERSHIP") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return raw in {"1", "true", "yes", "on"} or demo_tokens_disabled()


def document_parser_backend() -> str:
    """light (pypdf/docx/pptx), docling (prefer Docling), auto (Docling when installed)."""
    load_dotenv()
    raw = (os.environ.get("ARBOR_DOCUMENT_PARSER") or "light").strip().lower()
    if raw in {"light", "docling", "auto"}:
        return raw
    return "light"


def libreoffice_path() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_LIBREOFFICE_PATH") or "").strip()


def feishu_app_id() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_FEISHU_APP_ID") or os.environ.get("FEISHU_APP_ID") or "").strip()


def feishu_app_secret() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_FEISHU_APP_SECRET") or os.environ.get("FEISHU_APP_SECRET") or "").strip()


def feishu_redirect_uri() -> str:
    load_dotenv()
    return (
        os.environ.get("ARBOR_FEISHU_REDIRECT_URI")
        or "http://localhost:8000/v1/auth/feishu/callback"
    ).strip()


def feishu_web_success_url() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_WEB_URL") or "http://localhost:5173").rstrip("/")


def calendar_backend() -> str:
    """stub | feishu | auto — auto uses feishu when app credentials are set."""
    load_dotenv()
    raw = (os.environ.get("ARBOR_CALENDAR_BACKEND") or "auto").strip().lower()
    if raw in {"stub", "feishu", "auto"}:
        return raw
    return "auto"
