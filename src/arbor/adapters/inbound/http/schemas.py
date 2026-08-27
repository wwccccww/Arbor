from __future__ import annotations

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    text: str = ""
    attachments: list = Field(default_factory=list)


class GrantsIn(BaseModel):
    grants: list = Field(default_factory=list)


class ConfirmIn(BaseModel):
    mark_key_event: bool = False


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str = ""


class PersonaIn(BaseModel):
    skin: str = "companion"
    display_name: str = ""
    one_liner: str = ""
    personality: dict | None = None
    taboos: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    template: str | None = None
    avatar: str = ""


class PersonaPatchIn(BaseModel):
    skin: str | None = None
    display_name: str | None = None
    one_liner: str | None = None
    personality: dict | None = None
    taboos: list[str] | None = None
    relationships: list[dict] | None = None
    tool_policy: dict | None = None
    avatar: str | None = None


class PersonaEvalIn(BaseModel):
    strategy: str = "layered_tree"


class TicketToolIn(BaseModel):
    title: str = ""
    description: str = ""


class CalendarToolIn(BaseModel):
    query_text: str = "近期日程"


class MemberPatchIn(BaseModel):
    role: str


class TenantIn(BaseModel):
    name: str = ""


class MemberIn(BaseModel):
    email: str
    role: str = "member"


class EvalRunIn(BaseModel):
    strategy: str
    suite_version: str
    mode: str = "retrieval"
