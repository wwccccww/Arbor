from __future__ import annotations

from arbor.application.agent.employee_templates import default_employee_templates
from arbor.domain.shared.ids import PersonaId


def test_employee_templates_differ_in_tool_and_approval_policy():
    store = default_employee_templates()
    customer = store.get(PersonaId("template-customer-service"))
    tutor = store.get(PersonaId("template-tutor"))
    interviewer = store.get(PersonaId("template-interviewer"))
    assert customer is not None
    assert tutor is not None
    assert interviewer is not None
    assert customer.tool_policy.get("allowed_tools") != tutor.tool_policy.get("allowed_tools")
    assert customer.approval_policy != tutor.approval_policy
    assert customer.escalation_policy.get("user_escalation") == "handoff_human"
    assert tutor.escalation_policy.get("high_risk_action") == "deny"
    assert interviewer.escalation_policy.get("final_decision") == "human_required"
    assert interviewer.approval_policy.get("final_decision") is True
    assert customer.evaluation_suite == "agent-v1"
