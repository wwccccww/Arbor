from __future__ import annotations

from arbor.application.conversation.context_injection import select_profile_fields


def test_select_profile_fields_keeps_display_name_only_by_default():
    profile = {
        "display_name": "林夏",
        "one_liner": "住在杭州的陪伴助手",
        "taboos": ["香菜"],
    }
    selected = select_profile_fields("what happened at the noodle shop?", profile)
    assert selected == {"display_name": "林夏"}


def test_select_profile_fields_includes_taboos_for_food_query():
    profile = {"display_name": "林夏", "taboos": ["香菜"], "one_liner": "助手"}
    selected = select_profile_fields("点餐不能放什么", profile)
    assert selected["taboos"] == ["香菜"]


def test_select_profile_fields_includes_one_liner_for_residence_query():
    profile = {"display_name": "林夏", "one_liner": "住在杭州", "taboos": ["香菜"]}
    selected = select_profile_fields("Where does Lin Xia reside?", profile)
    assert selected["one_liner"] == "住在杭州"


def test_select_profile_fields_includes_taboos_for_durian_or_allergy():
    profile = {"display_name": "林夏", "taboos": ["榴莲"]}
    selected = select_profile_fields("What is his stance on durian?", profile)
    assert selected["taboos"] == ["榴莲"]
