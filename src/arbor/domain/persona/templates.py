from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PersonaTemplate:
    id: str
    label: str
    skin: str
    display_name: str
    one_liner: str
    personality: dict | None
    taboos: list[str]
    relationships: list[dict]


PERSONA_TEMPLATES: dict[str, PersonaTemplate] = {
    "companion_partner": PersonaTemplate(
        id="companion_partner",
        label="伴侣",
        skin="companion",
        display_name="",
        one_liner="温柔陪伴，记得你的喜好与约定",
        personality={"traits": ["体贴", "会记仇但会和好"]},
        taboos=[],
        relationships=[{"name": "用户", "kind": "partner"}],
    ),
    "companion_mentor": PersonaTemplate(
        id="companion_mentor",
        label="导师",
        skin="companion",
        display_name="",
        one_liner="耐心引导，帮你拆解问题与复盘",
        personality={"traits": ["冷静", "结构化"]},
        taboos=[],
        relationships=[{"name": "用户", "kind": "student"}],
    ),
    "employee_support": PersonaTemplate(
        id="employee_support",
        label="客服",
        skin="employee",
        display_name="",
        one_liner="按手册处理售后与退货",
        personality={"traits": ["简短", "按流程"]},
        taboos=[],
        relationships=[{"name": "用户", "kind": "customer"}],
    ),
    "employee_interviewer": PersonaTemplate(
        id="employee_interviewer",
        label="面试官",
        skin="employee",
        display_name="",
        one_liner="结构化提问，追问细节与动机",
        personality={"traits": ["直接", "追问细节"]},
        taboos=[],
        relationships=[{"name": "候选人", "kind": "interviewee"}],
    ),
}


def apply_template(template_id: str | None, **overrides) -> dict:
    """Merge a named template with explicit persona fields."""
    base: dict[str, Any] = {
        "skin": "companion",
        "display_name": "",
        "one_liner": "",
        "personality": None,
        "taboos": [],
        "relationships": [],
    }
    if template_id:
        tpl = PERSONA_TEMPLATES.get(template_id)
        if tpl is None:
            from arbor.domain.errors import DomainError

            raise DomainError("VALIDATION_ERROR", "unknown template")
        patch: dict[str, Any] = {
            "skin": tpl.skin,
            "display_name": tpl.display_name,
            "one_liner": tpl.one_liner,
            "personality": tpl.personality,
            "taboos": list(tpl.taboos),
            "relationships": list(tpl.relationships),
        }
        base.update(patch)
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base
