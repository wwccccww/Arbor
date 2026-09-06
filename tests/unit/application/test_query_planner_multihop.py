from __future__ import annotations

from arbor.application.query_planner import plan_queries


def test_multihop_splits_on_and():
    planned = plan_queries(
        "What does 林夏 usually do on weekends and what pet does 林夏 keep?",
        "rules",
    )
    assert len(planned) >= 2
    joined = " ".join(item["query"] for item in planned)
    assert "weekend" in joined.lower() or "周末" in joined
    assert "pet" in joined.lower() or "宠物" in joined


def test_multihop_splits_chinese_question_marks():
    planned = plan_queries("林夏在上海的周末通常做什么？他是否养宠物？", "rules")
    assert len(planned) >= 2
    assert any("周末" in item["query"] for item in planned)
    assert any("宠物" in item["query"] for item in planned)


def test_dietary_query_maps_to_profile_intent():
    planned = plan_queries(
        "Based on the provided facts, what are Lin Xia's dietary restrictions regarding cilantro and spice level?",
        "rules",
    )
    assert any(item["intent"] == "profile" for item in planned)


def test_allergy_birthday_tea_map_to_profile_intent():
    assert plan_queries("林夏对什么过敏？", "rules")[0]["intent"] == "profile"
    assert plan_queries("林夏的生日是哪一天？", "rules")[0]["intent"] == "profile"
    assert plan_queries("林夏日常喝什么茶？", "rules")[0]["intent"] == "profile"


def test_ticket_invoice_splits_and_marks_policy():
    planned = plan_queries("工单 #8842 升级后，承诺三日内补发充电器，那发票怎么给？", "rules")
    assert len(planned) >= 2
    intents = {item["intent"] for item in planned}
    assert "policy" in intents
    assert any("发票" in item["query"] for item in planned)


def test_garbled_english_normalizes_before_planning():
    planned = plan_queries(
        "hEy, cAn U tElL mE wHaT hApPeNs To OvErTiMe WoRk OrDeRs AfTeR 9 Pm?",
        "rules",
    )
    joined = " ".join(item["query"] for item in planned)
    assert "overtime" in joined
    assert any(item["intent"] == "policy" for item in planned)
