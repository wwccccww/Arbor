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


def judge_base_url() -> str:
    load_dotenv()
    raw = (
        os.environ.get("ARBOR_JUDGE_BASE_URL")
        or os.environ.get("SILICONFLOW_BASE_URL")
        or "https://api.siliconflow.cn/v1"
    )
    return raw.rstrip("/")


def judge_model() -> str:
    load_dotenv()
    return os.environ.get("ARBOR_JUDGE_MODEL", "Qwen/Qwen2.5-7B-Instruct")


def judge_embedding_model() -> str:
    load_dotenv()
    return os.environ.get("ARBOR_JUDGE_EMBEDDING_MODEL") or embedding_model()


def judge_status() -> str:
    """Why RAGAS faithfulness may be skipped: configured | missing_key | same_as_generator."""
    load_dotenv()
    judge = os.environ.get("ARBOR_JUDGE_API_KEY") or ""
    if not judge:
        return "missing_key"
    if judge == chat_api_key():
        return "same_as_generator"
    return "configured"


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


def ticket_api_url() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_TICKET_API_URL") or "").strip()


def ticket_api_key() -> str:
    load_dotenv()
    return (os.environ.get("ARBOR_TICKET_API_KEY") or "").strip()


def ticket_backend() -> str:
    """stub | http | auto — auto uses http when ARBOR_TICKET_API_URL is set."""
    load_dotenv()
    raw = (os.environ.get("ARBOR_TICKET_BACKEND") or "auto").strip().lower()
    if raw in {"stub", "http", "auto"}:
        return raw
    return "auto"


def tool_mode() -> str:
    """keywords | llm | both — how persona tools are invoked."""
    load_dotenv()
    raw = (os.environ.get("ARBOR_TOOL_MODE") or "both").strip().lower()
    if raw in {"keywords", "llm", "both"}:
        return raw
    return "both"


def context_window_tokens() -> int:
    load_dotenv()
    raw = (os.environ.get("ARBOR_CONTEXT_WINDOW_TOKENS") or "64000").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 64000
    return max(4096, value)


def context_max_output_tokens() -> int:
    load_dotenv()
    raw = (os.environ.get("ARBOR_CONTEXT_MAX_OUTPUT_TOKENS") or "2048").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 2048
    return max(256, value)


def context_recent_k() -> int:
    load_dotenv()
    raw = (os.environ.get("ARBOR_CONTEXT_RECENT_K") or "6").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 6
    return max(0, min(value, 32))


def context_system_overhead_tokens() -> int:
    load_dotenv()
    raw = (os.environ.get("ARBOR_CONTEXT_SYSTEM_OVERHEAD") or "600").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 600
    return max(200, value)


def _retrieval_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    load_dotenv()
    raw = (os.environ.get(name) or str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _retrieval_float(name: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    load_dotenv()
    raw = (os.environ.get(name) or str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def retrieval_pool_k() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_POOL_K", 24, minimum=5, maximum=100)


def retrieval_rerank_k() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_RERANK_K", 6, minimum=1, maximum=20)


def retrieval_prompt_k() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_PROMPT_K", 5, minimum=1, maximum=12)


def retrieval_event_seed_k() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_EVENT_SEED_K", 2, minimum=1, maximum=5)


def retrieval_event_expand_depth() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_EVENT_EXPAND_DEPTH", 2, minimum=0, maximum=4)


def retrieval_event_expand_max() -> int:
    return _retrieval_int("ARBOR_RETRIEVAL_EVENT_EXPAND_MAX", 8, minimum=2, maximum=32)


def retrieval_hybrid_enabled() -> bool:
    load_dotenv()
    raw = (os.environ.get("ARBOR_RETRIEVAL_HYBRID") or "on").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def retrieval_query_plan() -> str:
    load_dotenv()
    raw = (os.environ.get("ARBOR_RETRIEVAL_QUERY_PLAN") or "rules").strip().lower()
    if raw in {"off", "rules", "llm"}:
        return raw
    return "rules"


def retrieval_mmr_lambda() -> float:
    return _retrieval_float("ARBOR_RETRIEVAL_MMR_LAMBDA", 0.7)


def retrieval_type_weight_fact() -> float:
    return _retrieval_float("ARBOR_RETRIEVAL_TYPE_WEIGHT_FACT", 1.0, maximum=2.0)


def retrieval_type_weight_chunk() -> float:
    return _retrieval_float("ARBOR_RETRIEVAL_TYPE_WEIGHT_CHUNK", 0.6, maximum=2.0)


def chunk_max_chars() -> int:
    return _retrieval_int("ARBOR_CHUNK_MAX_CHARS", 1200, minimum=200, maximum=8000)


def chunk_overlap_chars() -> int:
    return _retrieval_int("ARBOR_CHUNK_OVERLAP_CHARS", 150, minimum=0, maximum=1000)


def agent_compat_chat() -> bool:
    load_dotenv()
    return (os.environ.get("ARBOR_AGENT_COMPAT_CHAT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def allow_plan_script() -> bool:
    """plan_script is test/admin only unless explicitly enabled."""
    load_dotenv()
    return (os.environ.get("ARBOR_ALLOW_PLAN_SCRIPT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def working_memory_max_items() -> int:
    load_dotenv()
    raw = (os.environ.get("ARBOR_WORKING_MEMORY_MAX_ITEMS") or "32").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 32


def mcp_server_url() -> str | None:
    load_dotenv()
    raw = (os.environ.get("ARBOR_MCP_SERVER_URL") or "").strip()
    return raw or None
