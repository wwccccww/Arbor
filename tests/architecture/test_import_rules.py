from __future__ import annotations

import ast
import inspect
from pathlib import Path

from arbor.adapters.outbound.inmemory import InMemoryVectorIndex
from arbor.adapters.outbound.postgres import PgVectorIndex
from arbor.ports.outbound import VectorIndex

ROOT = Path(__file__).resolve().parents[2] / "src" / "arbor"

FORBIDDEN_DOMAIN = ("arbor.adapters", "arbor.application", "fastapi", "sqlalchemy")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _iter_py(folder: str):
    yield from (ROOT / folder).rglob("*.py")


def test_domain_does_not_import_adapters_or_frameworks():
    for path in _iter_py("domain"):
        for name in _imports(path):
            assert not any(name == forbidden or name.startswith(forbidden + ".") for forbidden in FORBIDDEN_DOMAIN), (
                path,
                name,
            )


def test_application_does_not_import_adapters():
    for path in _iter_py("application"):
        for name in _imports(path):
            assert not name.startswith("arbor.adapters"), (path, name)
            assert not name.startswith("alembic"), (path, name)
            assert name != "sqlalchemy" and not name.startswith("sqlalchemy."), (path, name)


def test_deepseek_adapter_does_not_import_postgres():
    deepseek = ROOT / "adapters" / "outbound" / "deepseek"
    if not deepseek.exists():
        return
    for path in deepseek.rglob("*.py"):
        for name in _imports(path):
            assert "postgres" not in name


def test_vector_index_search_requires_tenant_and_persona():
    for target in (InMemoryVectorIndex.search, VectorIndex.search, PgVectorIndex.search):
        params = inspect.signature(target).parameters
        assert "tenant_id" in params and "persona_id" in params
        assert params["tenant_id"].default is inspect.Parameter.empty
        assert params["persona_id"].default is inspect.Parameter.empty
    annotations = getattr(VectorIndex.search, "__annotations__", {})
    assert "tenant_id" in annotations
    assert "persona_id" in annotations
