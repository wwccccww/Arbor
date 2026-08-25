from arbor.domain.errors import DomainError
from arbor.domain.persona.templates import PERSONA_TEMPLATES, apply_template


def test_apply_template_merges_defaults():
    merged = apply_template(
        "employee_support",
        display_name="客服小周",
    )
    assert merged["skin"] == "employee"
    assert merged["display_name"] == "客服小周"
    assert "手册" in merged["one_liner"]


def test_apply_template_rejects_unknown():
    try:
        apply_template("not-a-template", display_name="x")
    except DomainError as exc:
        assert exc.code == "VALIDATION_ERROR"
    else:
        raise AssertionError("expected DomainError")


def test_templates_cover_product_skills():
    assert set(PERSONA_TEMPLATES) == {
        "companion_partner",
        "companion_mentor",
        "employee_support",
        "employee_interviewer",
    }
