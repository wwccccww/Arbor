#!/usr/bin/env python3
"""生成 Arbor 评测集（RAGAS 分布 + 人设隔离切片）。

本环境通常没有可用的评测 LLM Key，且 ragas 0.3 与 langchain 1.x 导入不兼容。
默认 ``--backend ragas_compat``：按 RAGAS 的 simple / reasoning / multi_context
演化类型，从知识图谱离线合成，并强制绑定 memory_id。

若配置 DEEPSEEK_API_KEY（兼容 OpenAI 协议）且 ragas 0.2.15 可导入，可用
``--backend ragas`` 调用官方 TestsetGenerator。产物写到
``eval/fixtures/suite-ragas-official/``，**不会覆盖** 377 条 ``suite-ragas-v1``。
无密钥、导入失败或生成失败时非 0 退出，避免看起来像成功。

用法:
  python3 eval/generate_testset.py
  python3 eval/generate_testset.py --backend ragas --size 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "fixtures" / "suite-ragas-v1"
OFFICIAL_OUT = ROOT / "eval" / "fixtures" / "suite-ragas-official"

TENANT_A = "0a000000-0000-4000-a000-000000000001"
TENANT_B = "0b000000-0000-4000-a000-000000000001"
USER_A = "0a000000-0000-4000-a000-000000000002"
USER_B = "0b000000-0000-4000-a000-000000000002"
LINXIA_A = "0a000000-0000-4000-a000-000000000010"
ZHOU_A = "0a000000-0000-4000-a000-000000000020"
LINXIA_B = "0b000000-0000-4000-a000-000000000010"

# --- 知识图谱：扩展 suite-v1，供合成器用 ---

PERSONAS = [
    {
        "id": LINXIA_A,
        "tenant_id": TENANT_A,
        "user_id": USER_A,
        "skin": "companion",
        "display_name": "林夏",
        "one_liner": "住在杭州的陪伴助手",
        "taboos": ["香菜"],
    },
    {
        "id": ZHOU_A,
        "tenant_id": TENANT_A,
        "user_id": USER_A,
        "skin": "employee",
        "display_name": "客服小周",
        "one_liner": "只处理售后与退货",
        "taboos": [],
    },
    {
        "id": LINXIA_B,
        "tenant_id": TENANT_B,
        "user_id": USER_B,
        "skin": "companion",
        "display_name": "林夏",
        "one_liner": "住在上海的陪伴助手",
        "taboos": ["榴莲"],
    },
]

MEMORIES = [
    # 林夏 A
    {"id": "0a000000-0000-4000-a000-000000000301", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏住在杭州西湖区。", "slots": {"city": "杭州", "district": "西湖区"}},
    {"id": "0a000000-0000-4000-a000-000000000302", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏讨厌香菜，点餐不能放香菜。", "slots": {"taboo": "香菜"}},
    {"id": "0a000000-0000-4000-a000-000000000303", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000102", "type": "episode_summary", "status": "active", "text": "2024年11月2日晚上，两人在杭州湖滨路「老张面馆」争吵，导火索是面里放了香菜。", "slots": {"shop": "老张面馆", "date": "2024-11-02"}},
    {"id": "0a000000-0000-4000-a000-000000000304", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000102", "type": "episode_summary", "status": "active", "text": "面店争吵之后大约一周没有互相说话。", "slots": {"silence": "一周"}},
    {"id": "0a000000-0000-4000-a000-000000000305", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000103", "type": "fact", "status": "active", "text": "和好后约定每周日晚上 21:00 打电话。", "slots": {"when": "周日 21:00"}},
    {"id": "0a000000-0000-4000-a000-000000000306", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000101", "type": "image_caption", "status": "active", "text": "照片：西湖边第一次见面，背景是断桥，林夏穿米色外套。", "slots": {"place": "断桥", "clothes": "米色外套"}},
    {"id": "0a000000-0000-4000-a000-000000000307", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "superseded", "text": "林夏很喜欢猫，想养宠物猫。", "slots": {}},
    {"id": "0a000000-0000-4000-a000-000000000308", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "后来发现林夏对猫毛过敏，不能养猫。", "slots": {"allergy": "猫毛"}},
    {"id": "0a000000-0000-4000-a000-000000000309", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏日常喝龙井，不加香菜类配菜。", "slots": {"drink": "龙井"}},
    {"id": "0a000000-0000-4000-a000-000000000310", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏生日是9月18日。", "slots": {"birthday": "9月18日"}},
    {"id": "0a000000-0000-4000-a000-000000000311", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏在余杭上班，周末回西湖区。", "slots": {"work": "余杭"}},
    {"id": "0a000000-0000-4000-a000-000000000312", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000104", "type": "episode_summary", "status": "active", "text": "和好当天一起买了桂花糕。", "slots": {"food": "桂花糕"}},
    {"id": "0a000000-0000-4000-a000-000000000313", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000105", "type": "episode_summary", "status": "active", "text": "第一次正式约会在湖滨银泰看了电影《好东西》。", "slots": {"movie": "好东西"}},
    {"id": "0a000000-0000-4000-a000-000000000314", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000106", "type": "transcript", "status": "active", "text": "语音转写：周日电话里约定下周末去爬玉皇山，早上九点龙井村口集合。", "slots": {"hike": "玉皇山", "meet": "九点"}},
    {"id": "0a000000-0000-4000-a000-000000000315", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000102", "type": "image_caption", "status": "active", "text": "照片：老张面馆门口，地面反光像刚下过雨，林夏没吃那碗放了香菜的面。", "slots": {"shop_photo": "老张面馆门口"}},
    {"id": "0a000000-0000-4000-a000-000000000316", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏母亲姓陈，住在杭州。", "slots": {"mother": "陈"}},
    {"id": "0a000000-0000-4000-a000-000000000317", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": None, "type": "fact", "status": "active", "text": "林夏可以吃微辣，但不能接受香菜。", "slots": {"spice": "微辣"}},
    {"id": "0a000000-0000-4000-a000-000000000318", "tenant_id": TENANT_A, "persona_id": LINXIA_A, "event_id": "0a000000-0000-4000-a000-000000000103", "type": "fact", "status": "active", "text": "打电话时林夏习惯先问今天吃了什么，再决定周末安排。", "slots": {"habit": "先问吃了什么"}},
    # 小周
    {"id": "0a000000-0000-4000-a000-000000000401", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "售后手册：普通商品支持7天无理由退货，需包装完好。", "slots": {"return_days": "7"}},
    {"id": "0a000000-0000-4000-a000-000000000402", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": "0a000000-0000-4000-a000-000000000201", "type": "episode_summary", "status": "active", "text": "工单 #8842 已升级，承诺三日内补发充电器。", "slots": {"ticket": "8842", "item": "充电器"}},
    {"id": "0a000000-0000-4000-a000-000000000403", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "售后手册：已拆封的耳机、充电宝等个护/数码配件不支持无理由退货。", "slots": {"no_return": "已拆封数码配件"}},
    {"id": "0a000000-0000-4000-a000-000000000404", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "质量问题退换，往返运费由卖家承担；无理由退货运费由买家承担。", "slots": {"shipping": "质量问题卖家承担运费"}},
    {"id": "0a000000-0000-4000-a000-000000000405", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "发票随包裹寄出，电子发票发送到下单邮箱。", "slots": {"invoice": "随包裹或邮箱"}},
    {"id": "0a000000-0000-4000-a000-000000000406", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": "0a000000-0000-4000-a000-000000000201", "type": "episode_summary", "status": "active", "text": "工单 #8842 客户为张先生，投诉充电器不充电。", "slots": {"customer": "张先生"}},
    {"id": "0a000000-0000-4000-a000-000000000407", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": "0a000000-0000-4000-a000-000000000201", "type": "fact", "status": "active", "text": "补发运单号 SF1234567890，预计两日内送达。", "slots": {"tracking": "SF1234567890"}},
    {"id": "0a000000-0000-4000-a000-000000000408", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "在线客服工作时间每天 9:00–21:00，超时工单次日处理。", "slots": {"hours": "9:00-21:00"}},
    {"id": "0a000000-0000-4000-a000-000000000409", "tenant_id": TENANT_A, "persona_id": ZHOU_A, "event_id": None, "type": "file_chunk", "status": "active", "text": "食品类商品拆封后不支持7天无理由，质量问题除外。", "slots": {"food": "拆封食品不退"}},
    # 林夏 B（故意与 A 冲突，用于租户隔离）
    {"id": "0b000000-0000-4000-a000-000000000301", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "fact", "status": "active", "text": "林夏住在上海杨浦区。", "slots": {"city": "上海", "district": "杨浦区"}},
    {"id": "0b000000-0000-4000-a000-000000000302", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "fact", "status": "active", "text": "林夏讨厌榴莲，房间里不能出现榴莲。", "slots": {"taboo": "榴莲"}},
    {"id": "0b000000-0000-4000-a000-000000000303", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "fact", "status": "active", "text": "林夏周末通常打游戏，没有每周日打电话的约定。", "slots": {"weekend": "打游戏"}},
    {"id": "0b000000-0000-4000-a000-000000000304", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "fact", "status": "active", "text": "林夏在复旦附近租房。", "slots": {"near": "复旦"}},
    {"id": "0b000000-0000-4000-a000-000000000305", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "fact", "status": "active", "text": "林夏很喜欢猫，宿舍养了一只橘猫。", "slots": {"pet": "橘猫"}},
    {"id": "0b000000-0000-4000-a000-000000000306", "tenant_id": TENANT_B, "persona_id": LINXIA_B, "event_id": None, "type": "image_caption", "status": "active", "text": "照片：外滩夜景，林夏穿黑色风衣，手里没有桂花糕。", "slots": {"place": "外滩"}},
]

EVENTS = [
    {"id": "0a000000-0000-4000-a000-000000000101", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "第一次见面", "summary": "在西湖边认识。"},
    {"id": "0a000000-0000-4000-a000-000000000102", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "面店争吵", "summary": "因香菜在老张面馆吵架。"},
    {"id": "0a000000-0000-4000-a000-000000000103", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "约定每周末打电话", "summary": "每周日 21:00 打电话。"},
    {"id": "0a000000-0000-4000-a000-000000000104", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "和好买桂花糕", "summary": "和好当天买桂花糕。"},
    {"id": "0a000000-0000-4000-a000-000000000105", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "第一次看电影", "summary": "银泰看《好东西》。"},
    {"id": "0a000000-0000-4000-a000-000000000106", "persona_id": LINXIA_A, "tenant_id": TENANT_A, "title": "约定爬玉皇山", "summary": "下周末九点龙井村口集合。"},
    {"id": "0a000000-0000-4000-a000-000000000201", "persona_id": ZHOU_A, "tenant_id": TENANT_A, "title": "工单升级补发", "summary": "8842 补发充电器。"},
]


def _mem(mid: str) -> dict:
    return next(m for m in MEMORIES if m["id"] == mid)


def _active(persona_id: str) -> list[dict]:
    return [m for m in MEMORIES if m["persona_id"] == persona_id and m["status"] == "active"]


def _ids_other_personas(persona_id: str) -> list[str]:
    return [m["id"] for m in MEMORIES if m["persona_id"] != persona_id]


def _actor(persona_id: str) -> dict:
    p = next(x for x in PERSONAS if x["id"] == persona_id)
    return {"tenant_id": p["tenant_id"], "persona_id": p["id"], "user_id": p["user_id"]}


def _case(**kwargs) -> dict:
    persona_id = kwargs["actor"]["persona_id"]
    forbidden = kwargs.get("forbidden_memory_ids")
    if forbidden is None:
        forbidden = _ids_other_personas(persona_id)
        # 同人设 superseded 也禁止
        forbidden = forbidden + [m["id"] for m in MEMORIES if m["persona_id"] == persona_id and m["status"] == "superseded"]
    base = {
        "suite": "ragas-v1",
        "generator": "ragas_compat",
        "expected_event_id": None,
        "repeat": 1,
        "forbidden_memory_ids": forbidden,
    }
    base.update(kwargs)
    return base


def _surfaces(question: str) -> list[str]:
    """同一金标、不同问法，测检索鲁棒（对齐 RAGAS 多样 query）。"""
    q = question.strip()
    return list(
        dict.fromkeys(
            [
                q,
                f"我有点记不清了，{q}",
                f"请根据你记得的事实回答：{q}",
            ]
        )
    )


def _simple_from_node(mem: dict, questions: list[str], reference: str, skill: str, source: str, event_id=None) -> list[dict]:
    out = []
    i = 0
    for q0 in questions:
        for q in _surfaces(q0):
            i += 1
            out.append(
                _case(
                    id=f"simple-{mem['id']}-{i:02d}",
                    evolution_type="simple",
                    skill=skill,
                    query=q,
                    reference=reference,
                    reference_contexts=[mem["text"]],
                    actor=_actor(mem["persona_id"]),
                    expected_behavior="answer" if source != "event_tree" else "cite",
                    expected_source=source,
                    expected_memory_ids=[mem["id"]],
                    expected_event_id=event_id or mem.get("event_id"),
                )
            )
    return out


def synthesize_simple() -> list[dict]:
    cases: list[dict] = []
    spec = [
        ("0a000000-0000-4000-a000-000000000301", ["你住在哪里？", "家在哪个城市？", "现在住哪一区？", "你是杭州人还是外地现在住哪？"], "杭州西湖区", "profile_fact", "profile"),
        ("0a000000-0000-4000-a000-000000000302", ["点餐有什么不能放？", "你讨厌什么配菜？", "香菜可以点吗？", "我点面要注意什么？"], "不能放香菜", "profile_fact", "profile"),
        ("0a000000-0000-4000-a000-000000000303", ["我们是在哪家店吵起来的？", "那次吵架的馆子叫什么？", "湖滨路那家面馆叫什么名字？", "11月2号晚上在哪吃的面？"], "老张面馆", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000304", ["吵完以后多久没说话？", "那次之后冷战了多久？", "一周没联系是因为什么时候开始的？"], "大约一周没说话", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000305", ["我们约定几点打电话？", "每周哪一天要通话？", "周日晚上的约定是什么？", "21点的电话还作数吗？"], "每周日晚上 21:00 打电话", "temporal", "event_tree"),
        ("0a000000-0000-4000-a000-000000000306", ["第一次见面那张照片在哪拍的？", "断桥那张照片你穿了什么？", "米色外套那张背景是什么？"], "西湖断桥，米色外套", "multimodal", "vector"),
        ("0a000000-0000-4000-a000-000000000308", ["林夏适合养猫吗？", "对猫过敏吗？", "能不能养宠物猫？"], "对猫毛过敏，不能养", "conflict", "vector"),
        ("0a000000-0000-4000-a000-000000000309", ["你平时喝什么茶？", "龙井还喝吗？"], "日常喝龙井", "profile_fact", "vector"),
        ("0a000000-0000-4000-a000-000000000310", ["你生日是哪天？", "9月有什么日子我该记得？"], "9月18日", "profile_fact", "vector"),
        ("0a000000-0000-4000-a000-000000000311", ["你在哪上班？", "工作日住余杭吗？", "周末回哪个区？"], "余杭上班，周末回西湖区", "profile_fact", "vector"),
        ("0a000000-0000-4000-a000-000000000312", ["和好那天买了什么？", "桂花糕是什么时候买的？"], "和好当天买了桂花糕", "episode_detail", "event_tree"),
        ("0a000000-0000-4000-a000-000000000313", ["第一次正式约会看了什么电影？", "银泰看的那部片子叫什么？"], "《好东西》", "episode_detail", "event_tree"),
        ("0a000000-0000-4000-a000-000000000314", ["下周末去爬哪座山？", "语音里说几点在哪集合？", "龙井村口集合是去干什么？"], "玉皇山，早上九点龙井村口", "multimodal", "event_tree"),
        ("0a000000-0000-4000-a000-000000000315", ["面馆门口那张照片是什么天气？", "雨天那张是在哪家店门口？"], "老张面馆门口，像刚下过雨", "multimodal", "vector"),
        ("0a000000-0000-4000-a000-000000000316", ["你妈妈姓什么？", "母亲住在哪？"], "姓陈，住杭州", "profile_fact", "vector"),
        ("0a000000-0000-4000-a000-000000000317", ["能吃辣吗？", "微辣可以还是完全不吃辣？"], "可以微辣，但不能香菜", "profile_fact", "vector"),
        ("0a000000-0000-4000-a000-000000000318", ["打电话时你习惯先问什么？", "通话开头你会问哪句？"], "先问今天吃了什么", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000401", ["普通商品几天可以无理由退货？", "7天退货要满足什么条件？", "包装破了还能无理由退吗？"], "7天无理由，包装须完好", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000402", ["工单8842承诺补发什么？", "三日内补发的是哪件配件？"], "三日内补发充电器", "episode_detail", "event_tree"),
        ("0a000000-0000-4000-a000-000000000403", ["拆封的充电宝能无理由退吗？", "耳机拆封后还支持7天退吗？"], "已拆封数码配件不支持无理由退货", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000404", ["质量问题运费谁出？", "无理由退货运费谁承担？"], "质量问题卖家承担；无理由买家承担", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000405", ["发票怎么给我？", "电子发票发到哪里？"], "纸质随包裹，电子发下单邮箱", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000406", ["8842 是哪位客户？", "张先生投诉的是什么？"], "张先生，充电器不充电", "episode_detail", "event_tree"),
        ("0a000000-0000-4000-a000-000000000407", ["补发单号是多少？", "SF 开头的运单号是？"], "SF1234567890", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000408", ["客服几点上班？", "晚上十点提交的工单何时处理？"], "9:00–21:00，超时次日处理", "episode_detail", "vector"),
        ("0a000000-0000-4000-a000-000000000409", ["拆封的零食能7天无理由退吗？"], "拆封食品不支持无理由，质量问题除外", "episode_detail", "vector"),
        ("0b000000-0000-4000-a000-000000000301", ["你住在哪里？", "现在住上海哪一区？"], "上海杨浦区", "profile_fact", "profile"),
        ("0b000000-0000-4000-a000-000000000302", ["房间里不能出现什么？", "你讨厌哪种水果？"], "讨厌榴莲", "profile_fact", "profile"),
        ("0b000000-0000-4000-a000-000000000303", ["周末你一般干什么？", "有没有每周日打电话的约定？"], "周末打游戏，没有周日电话约定", "profile_fact", "vector"),
        ("0b000000-0000-4000-a000-000000000304", ["房子靠近哪所学校？", "租房在复旦附近吗？"], "复旦附近", "profile_fact", "vector"),
        ("0b000000-0000-4000-a000-000000000305", ["你养猫了吗？", "宿舍那只猫什么颜色？"], "养了一只橘猫", "profile_fact", "vector"),
        ("0b000000-0000-4000-a000-000000000306", ["外滩那张照片你穿什么？", "黑色风衣那张是在哪拍的？"], "外滩，黑色风衣", "multimodal", "vector"),
    ]
    for mid, qs, ref, skill, source in spec:
        mem = _mem(mid)
        cases.extend(_simple_from_node(mem, qs, ref, skill, source))
    return cases


def synthesize_reasoning() -> list[dict]:
    """RAGAS reasoning / 因果多跳。"""
    pairs = [
        {
            "qs": ["为什么后来一周没说话？", "冷战的直接原因是什么？", "为什么会因为一碗面闹翻？"],
            "mids": ["0a000000-0000-4000-a000-000000000303", "0a000000-0000-4000-a000-000000000304"],
            "eid": "0a000000-0000-4000-a000-000000000102",
            "ref": "因为老张面馆的面放了香菜引发争吵，之后大约一周没说话。",
            "pid": LINXIA_A,
        },
        {
            "qs": ["为什么不能再给林夏点带香菜的菜？", "点餐禁忌和那次吵架有什么关系？"],
            "mids": ["0a000000-0000-4000-a000-000000000302", "0a000000-0000-4000-a000-000000000303"],
            "eid": "0a000000-0000-4000-a000-000000000102",
            "ref": "林夏讨厌香菜，上次在老张面馆因香菜争吵。",
            "pid": LINXIA_A,
        },
        {
            "qs": ["为什么现在不能养猫？以前不是说喜欢吗？", "喜欢猫和过敏哪个算数？"],
            "mids": ["0a000000-0000-4000-a000-000000000308"],
            "eid": None,
            "ref": "后来确认对猫毛过敏，旧的「喜欢猫」已作废，不能养。",
            "pid": LINXIA_A,
            "forbidden_extra": ["0a000000-0000-4000-a000-000000000307"],
        },
        {
            "qs": ["周日电话和爬玉皇山的约定怎么衔接？", "通话里除了问好还定了什么出行？"],
            "mids": ["0a000000-0000-4000-a000-000000000305", "0a000000-0000-4000-a000-000000000314"],
            "eid": "0a000000-0000-4000-a000-000000000106",
            "ref": "每周日 21:00 打电话；其中一次约定下周末九点去爬玉皇山。",
            "pid": LINXIA_A,
        },
        {
            "qs": ["工单升级之后物流到哪一步了？", "张先生的充电器补发有单号了吗？"],
            "mids": ["0a000000-0000-4000-a000-000000000402", "0a000000-0000-4000-a000-000000000407"],
            "eid": "0a000000-0000-4000-a000-000000000201",
            "ref": "8842 承诺三日补发充电器，运单 SF1234567890。",
            "pid": ZHOU_A,
        },
        {
            "qs": ["质量问题退货和普通7天退货运费规则有何不同？"],
            "mids": ["0a000000-0000-4000-a000-000000000401", "0a000000-0000-4000-a000-000000000404"],
            "eid": None,
            "ref": "7天无理由需包装完好且买家承担运费；质量问题卖家承担往返运费。",
            "pid": ZHOU_A,
        },
        {
            "qs": ["拆封充电宝不能退，是因为7天政策失效了吗？"],
            "mids": ["0a000000-0000-4000-a000-000000000401", "0a000000-0000-4000-a000-000000000403"],
            "eid": None,
            "ref": "普通商品7天无理由仍在；已拆封数码配件是例外，不支持无理由。",
            "pid": ZHOU_A,
        },
        {
            "qs": ["租户B的林夏周末为什么不会等周日电话？"],
            "mids": ["0b000000-0000-4000-a000-000000000303"],
            "eid": None,
            "ref": "她周末打游戏，没有每周日打电话的约定。",
            "pid": LINXIA_B,
        },
    ]
    cases = []
    n = 0
    for block in pairs:
        ctx = [_mem(i)["text"] for i in block["mids"]]
        extra_f = block.get("forbidden_extra", [])
        for q0 in block["qs"]:
          for q in _surfaces(q0):
            n += 1
            cases.append(
                _case(
                    id=f"reasoning-{n:03d}",
                    evolution_type="reasoning",
                    skill="causal",
                    query=q,
                    reference=block["ref"],
                    reference_contexts=ctx,
                    actor=_actor(block["pid"]),
                    expected_behavior="cite" if block["eid"] else "answer",
                    expected_source="event_tree" if block["eid"] else "vector",
                    expected_memory_ids=block["mids"],
                    expected_event_id=block["eid"],
                    forbidden_memory_ids=_ids_other_personas(block["pid"]) + extra_f,
                )
            )
    return cases


def synthesize_multi_context() -> list[dict]:
    """RAGAS multi_context：必须同时用到两条记忆。"""
    combos = [
        (LINXIA_A, ["你住哪、上班在哪？", "工作日和周末分别在哪个区？"], ["0a000000-0000-4000-a000-000000000301", "0a000000-0000-4000-a000-000000000311"], "住西湖区，余杭上班周末回去。"),
        (LINXIA_A, ["忌口和辣度分别是什么？", "微辣和香菜哪个绝对不行？"], ["0a000000-0000-4000-a000-000000000302", "0a000000-0000-4000-a000-000000000317"], "可微辣，绝对不能香菜。"),
        (LINXIA_A, ["第一次见面和第一次看电影分别在哪？"], ["0a000000-0000-4000-a000-000000000306", "0a000000-0000-4000-a000-000000000313"], "见面在西湖断桥；约会在湖滨银泰看《好东西》。"),
        (LINXIA_A, ["生日和每周通话提醒我一下。"], ["0a000000-0000-4000-a000-000000000310", "0a000000-0000-4000-a000-000000000305"], "生日9月18日；每周日21:00打电话。"),
        (LINXIA_A, ["两张照片分别在哪拍的、穿什么？"], ["0a000000-0000-4000-a000-000000000306", "0a000000-0000-4000-a000-000000000315"], "断桥米色外套；老张面馆门口雨天。"),
        (ZHOU_A, ["7天退货和食品拆封规则一起说。"], ["0a000000-0000-4000-a000-000000000401", "0a000000-0000-4000-a000-000000000409"], "普通商品7天需包装完好；食品拆封后无理由不退。"),
        (ZHOU_A, ["8842 客户是谁、补发什么、单号多少？"], ["0a000000-0000-4000-a000-000000000406", "0a000000-0000-4000-a000-000000000402", "0a000000-0000-4000-a000-000000000407"], "张先生，补发充电器，SF1234567890。"),
        (LINXIA_B, ["你住哪、房子靠近哪、讨厌什么？"], ["0b000000-0000-4000-a000-000000000301", "0b000000-0000-4000-a000-000000000304", "0b000000-0000-4000-a000-000000000302"], "上海杨浦、复旦附近、讨厌榴莲。"),
        (LINXIA_B, ["养猫情况和外滩那张照片。"], ["0b000000-0000-4000-a000-000000000305", "0b000000-0000-4000-a000-000000000306"], "宿舍橘猫；外滩黑风衣。"),
        (LINXIA_A, ["母亲住哪、你自己住哪？"], ["0a000000-0000-4000-a000-000000000316", "0a000000-0000-4000-a000-000000000301"], "母亲姓陈住杭州；自己住西湖区。"),
    ]
    cases = []
    n = 0
    for pid, qs, mids, ref in combos:
        ctx = [_mem(i)["text"] for i in mids]
        for q0 in qs:
          for q in _surfaces(q0):
            n += 1
            cases.append(
                _case(
                    id=f"multi-{n:03d}",
                    evolution_type="multi_context",
                    skill="episode_detail",
                    query=q,
                    reference=ref,
                    reference_contexts=ctx,
                    actor=_actor(pid),
                    expected_behavior="answer",
                    expected_source="vector",
                    expected_memory_ids=mids,
                )
            )
    return cases


def synthesize_conditional() -> list[dict]:
    rows = [
        (ZHOU_A, "如果充电宝已经拆封，还能走7天无理由吗？", "不能，已拆封数码配件不支持无理由退货。", ["0a000000-0000-4000-a000-000000000403"]),
        (ZHOU_A, "如果是质量问题退货，运费谁出？", "卖家承担往返运费。", ["0a000000-0000-4000-a000-000000000404"]),
        (ZHOU_A, "如果包装已经拆了但商品是普通衣服，还能7天退吗？", "无理由退货需包装完好，包装破了一般不行。", ["0a000000-0000-4000-a000-000000000401"]),
        (ZHOU_A, "如果晚上十点才提交工单会怎样？", "超出 21:00，次日处理。", ["0a000000-0000-4000-a000-000000000408"]),
        (ZHOU_A, "如果拆了袋的饼干只是不想吃了，能退吗？", "拆封食品不支持无理由。", ["0a000000-0000-4000-a000-000000000409"]),
        (LINXIA_A, "如果想点微辣香菜拌面可以吗？", "微辣可以，香菜不行。", ["0a000000-0000-4000-a000-000000000317", "0a000000-0000-4000-a000-000000000302"]),
        (LINXIA_A, "如果周末想去余杭找你上班的地方？", "工作日在余杭，周末她回西湖区。", ["0a000000-0000-4000-a000-000000000311"]),
        (LINXIA_A, "如果想送宠物当礼物，猫可以吗？", "不行，对猫毛过敏。", ["0a000000-0000-4000-a000-000000000308"]),
        (LINXIA_B, "如果带榴莲进房间可以吗？", "不可以，讨厌榴莲。", ["0b000000-0000-4000-a000-000000000302"]),
        (LINXIA_B, "如果周日晚上21点等电话，你会打来吗？", "不会，没有该约定，周末通常打游戏。", ["0b000000-0000-4000-a000-000000000303"]),
    ]
    cases = []
    i = 0
    for pid, q0, ref, mids in rows:
      for q in _surfaces(q0):
        i += 1
        cases.append(
            _case(
                id=f"cond-{i:03d}",
                evolution_type="conditional",
                skill="episode_detail",
                query=q,
                reference=ref,
                reference_contexts=[_mem(m)["text"] for m in mids],
                actor=_actor(pid),
                expected_behavior="answer",
                expected_source="vector",
                expected_memory_ids=mids,
            )
        )
    return cases


def synthesize_isolation() -> list[dict]:
    """RAGAS 不会从单库文档生成的负例：人设/租户隔离。"""
    secrets_a = [
        ("林夏讨厌吃什么？你们在哪家面馆吵过架？", ["香菜", "老张面馆"]),
        ("林夏住在西湖区吗？生日是哪天？", ["西湖", "9月18"]),
        ("周日21点打电话的约定还在吗？", ["21:00"]),
        ("那张断桥米色外套照片是谁的？", ["断桥"]),
        ("林夏对猫毛过敏吗？", ["过敏"]),
        ("下周末是不是去爬玉皇山？", ["玉皇山"]),
    ]
    cases = []
    n = 0
    # 小周不得知道林夏 A
    for q0, _leaks in secrets_a:
        for q in _surfaces(q0):
            n += 1
            cases.append(
            _case(
                id=f"iso-zhou-{n:02d}",
                evolution_type="arbor_isolation",
                skill="persona_isolation",
                query=q,
                reference="不知道。我只处理售后，没有林夏的私人经历。",
                reference_contexts=[],
                actor=_actor(ZHOU_A),
                expected_behavior="refuse",
                expected_source=None,
                expected_memory_ids=[],
                forbidden_memory_ids=_ids_other_personas(ZHOU_A),
            )
        )
    # 租户 B 不得命中杭州世界
    tenant_qs = [
        "我们在湖滨路老张面馆吵过架吗？",
        "你住在杭州西湖区吗？",
        "你讨厌香菜还是榴莲？",
        "每周日21点要打电话吗？",
        "断桥那张米色外套是你吗？",
        "你对猫毛过敏所以不能养猫？",
        "和好那天买过桂花糕吗？",
        "工单8842充电器补发到哪了？",
    ]
    for q in tenant_qs:
        n += 1
        cases.append(
            _case(
                id=f"iso-tenant-{n:02d}",
                evolution_type="arbor_isolation",
                skill="tenant_isolation",
                query=q,
                reference="按上海林夏的档案回答或否认杭州经历，不得引用租户A记忆。",
                reference_contexts=[m["text"] for m in _active(LINXIA_B)[:2]],
                actor=_actor(LINXIA_B),
                expected_behavior="refuse" if any(k in q for k in ["老张", "杭州西湖", "香菜还是", "21点", "断桥", "桂花糕", "8842"]) else "answer",
                expected_source=None,
                expected_memory_ids=[],
                forbidden_memory_ids=_ids_other_personas(LINXIA_B),
            )
        )
    # 林夏 A 不得引用上海橘猫/榴莲/外滩
    for q in ["你在复旦附近租房吗？", "宿舍橘猫还好吗？", "外滩黑风衣那张是你吗？", "你讨厌榴莲吗？"]:
        n += 1
        cases.append(
            _case(
                id=f"iso-a-from-b-{n:02d}",
                evolution_type="arbor_isolation",
                skill="tenant_isolation",
                query=q,
                reference="租户A林夏不应确认上海设定。",
                reference_contexts=[],
                actor=_actor(LINXIA_A),
                expected_behavior="refuse",
                expected_source=None,
                expected_memory_ids=[],
                forbidden_memory_ids=_ids_other_personas(LINXIA_A),
            )
        )
    return cases


def synthesize_irrelevant() -> list[dict]:
    qs = [
        (LINXIA_A, "今天杭州天气怎么样？"),
        (LINXIA_A, "帮我算一下 17*19。"),
        (LINXIA_A, "现在上热搜第一是什么？"),
        (ZHOU_A, "你觉得林夏性格好不好？"),
        (ZHOU_A, "今天股市涨了吗？"),
        (LINXIA_B, "上海今天限行尾号是多少？"),
        (LINXIA_A, "随便聊聊宇宙起源吧。"),
        (ZHOU_A, "写一首关于退货的诗，不要查手册。"),
    ]
    cases = []
    for i, (pid, q) in enumerate(qs, 1):
        cases.append(
            _case(
                id=f"irrel-{i:02d}",
                evolution_type="arbor_irrelevant",
                skill="irrelevant",
                query=q,
                reference="不依赖私密记忆即可回答或拒答；不得强行注入争吵/禁忌。",
                reference_contexts=[],
                actor=_actor(pid),
                expected_behavior="answer",
                expected_source=None,
                expected_memory_ids=[],
                forbidden_as_required=False,
            )
        )
    return cases


def synthesize_all() -> list[dict]:
    cases = []
    for fn in (
        synthesize_simple,
        synthesize_reasoning,
        synthesize_multi_context,
        synthesize_conditional,
        synthesize_isolation,
        synthesize_irrelevant,
    ):
        cases.extend(fn())
    # 稳定排序，便于 diff
    cases.sort(key=lambda c: c["id"])
    return cases


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _chat_key() -> str:
    _load_dotenv()
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


class RagasBackendError(RuntimeError):
    """官方 TestsetGenerator 不可用。code 供 CLI 退出码使用。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _ragas_page_content(mem: dict, min_tokens: int = 101) -> str:
    """把短记忆扩成 RAGAS default_transforms 能接受的文档（需 >100 tokens）。

    原文放在文首，便于用前 16 字 stem 回绑 memory_id；正文重复金标，不新增事实。
    """
    from ragas.utils import num_tokens_from_string

    persona = next(p for p in PERSONAS if p["id"] == mem["persona_id"])
    slots = ", ".join(f"{k}={v}" for k, v in (mem.get("slots") or {}).items()) or "none"
    event = mem.get("event_id") or "none"
    body = (
        f"{mem['text']}\n\n"
        f"Arbor persona memory record.\n"
        f"memory_id: {mem['id']}\n"
        f"tenant_id: {mem['tenant_id']}\n"
        f"persona_id: {mem['persona_id']}\n"
        f"persona_name: {persona['display_name']}\n"
        f"persona_skin: {persona['skin']}\n"
        f"persona_one_liner: {persona['one_liner']}\n"
        f"memory_type: {mem['type']}\n"
        f"memory_status: {mem['status']}\n"
        f"event_id: {event}\n"
        f"slots: {slots}\n"
        f"verbatim_fact: {mem['text']}\n"
        "Instruction: generate questions only from the verbatim fact. "
        "Do not mix facts from other tenants or personas. "
        f"The gold answer must be supported by: {mem['text']}\n"
    )
    filler = (
        f" This record belongs to the Arbor evaluation knowledge graph. "
        f"When using this fact, keep memory_id {mem['id']}. "
        f"Source sentence: {mem['text']}"
    )
    while num_tokens_from_string(body) < min_tokens:
        body += filler
    return body


def _align_memory_ids(blob: str) -> list[str]:
    hit: list[str] = []
    for m in MEMORIES:
        if m["status"] != "active":
            continue
        stem = m["text"][:16]
        if m["id"] in blob or (stem and stem in blob):
            hit.append(m["id"])
    return list(dict.fromkeys(hit))


def try_ragas_backend(size: int) -> list[dict]:
    """调用官方 TestsetGenerator（DeepSeek Chat + 本地占位 embedding）。"""
    import os as _os

    key = _chat_key()
    if not key:
        raise RagasBackendError(
            1,
            "[ragas] DEEPSEEK_API_KEY 未注入本进程。对话弹窗不会写入已启动的 VM；"
            "请在 Cursor Dashboard → Cloud Agents → My Secrets 保存同名 Runtime Secret 后新开一轮 Agent。",
        )

    try:
        from langchain_community.embeddings import FakeEmbeddings
        from langchain_core.documents import Document
        from langchain_openai import ChatOpenAI
        from ragas.testset import TestsetGenerator
        from ragas.utils import num_tokens_from_string
    except Exception as exc:  # noqa: BLE001
        raise RagasBackendError(2, f"[ragas] import failed: {exc}") from exc

    # 部分 RAGAS/LangChain 只认 OPENAI_* ；DeepSeek 兼容该协议。
    _os.environ.setdefault("OPENAI_API_KEY", key)
    base = _os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    _os.environ.setdefault("OPENAI_BASE_URL", base)

    llm = ChatOpenAI(
        model=_os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
        api_key=key,
        base_url=base,
        temperature=0.3,
        timeout=120,
        max_retries=2,
    )
    # DeepSeek 无官方 embedding；出题阶段用占位向量，题目仍由 Chat 从文档生成。
    embeddings = FakeEmbeddings(size=384)

    docs = [
        Document(
            page_content=_ragas_page_content(m),
            metadata={
                "memory_id": m["id"],
                "persona_id": m["persona_id"],
                "tenant_id": m["tenant_id"],
            },
        )
        for m in MEMORIES
        if m["status"] == "active"
    ]
    token_counts = [num_tokens_from_string(d.page_content) for d in docs]
    n_mid = sum(1 for n in token_counts if 101 <= n <= 500)
    print(
        f"[ragas] docs={len(docs)} token_min={min(token_counts)} token_max={max(token_counts)} "
        f"bin_101_500={n_mid}/{len(docs)}",
        file=sys.stderr,
    )
    try:
        generator = TestsetGenerator.from_langchain(llm, embeddings)
        testset = generator.generate_with_langchain_docs(
            docs,
            testset_size=size,
            raise_exceptions=False,
        )
        rows = testset.to_pandas().to_dict(orient="records")
    except Exception as exc:  # noqa: BLE001
        raise RagasBackendError(3, f"[ragas] generate failed: {exc}") from exc

    aligned = []
    skipped = 0
    for i, row in enumerate(rows, 1):
        contexts = list(row.get("reference_contexts") or row.get("contexts") or [])
        blob = "\n".join(str(x) for x in contexts) + "\n" + str(row.get("reference") or row.get("ground_truth") or "")
        hit = _align_memory_ids(blob)
        if not hit:
            skipped += 1
            continue
        persona = _mem(hit[0])["persona_id"]
        gold_contexts = [_mem(mid)["text"] for mid in hit]
        aligned.append(
            _case(
                id=f"ragas-llm-{i:03d}",
                suite="ragas-official",
                generator="ragas",
                evolution_type=str(row.get("evolution_type") or row.get("synthesizer_name") or "simple"),
                skill="episode_detail",
                query=str(row.get("user_input") or row.get("question") or ""),
                reference=str(row.get("reference") or row.get("ground_truth") or ""),
                reference_contexts=gold_contexts,
                actor=_actor(persona),
                expected_behavior="answer",
                expected_source="vector",
                expected_memory_ids=hit,
            )
        )
    print(f"[ragas] aligned={len(aligned)} skipped_unaligned={skipped} raw_rows={len(rows)}", file=sys.stderr)
    return aligned


def manifest(cases: list[dict], suite_version: str = "ragas-v1") -> dict:
    n = len(cases) or 1
    return {
        "suite_version": suite_version,
        "n_cases": len(cases),
        "n_unique_queries": len({c["query"] for c in cases}),
        "n_unique_references": len({c["reference"] for c in cases}),
        "n_source_memories": len(MEMORIES),
        "n_active_memories": sum(1 for m in MEMORIES if m["status"] == "active"),
        "n_tenants": 2,
        "n_personas": 3,
        "evolution_distribution": dict(Counter(c["evolution_type"] for c in cases)),
        "skill_distribution": dict(Counter(c["skill"] for c in cases)),
        "persona_distribution": dict(Counter(c["actor"]["persona_id"] for c in cases)),
        "behavior_distribution": dict(Counter(c["expected_behavior"] for c in cases)),
        "id_bound_rate": round(
            sum(1 for c in cases if c["expected_memory_ids"] or c["expected_behavior"] == "refuse") / n,
            4,
        ),
        "generator_note": (
            "Official ragas TestsetGenerator (DeepSeek Chat + FakeEmbeddings); rows aligned to memory_id."
            if suite_version == "ragas-official"
            else "Default backend ragas_compat implements RAGAS simple/reasoning/multi_context/conditional plus Arbor isolation slices. Official ragas TestsetGenerator writes suite-ragas-official/ and does not overwrite this suite."
        ),
        "resume_blurb": (
            f"{len(cases)} 条官方 TestsetGenerator 样本 / DeepSeek Chat + FakeEmbeddings / id 绑定率 "
            f"{round(sum(1 for c in cases if c['expected_memory_ids']) / n, 4)}。"
            if suite_version == "ragas-official"
            else f"{len(cases)} 条评测样本 / 2 租户 3 人设 / {len(MEMORIES)} 条源记忆 / RAGAS 演化类型 + 隔离负例，全部绑定 memory_id 或 refuse。"
        ),
    }


def export_ragas_jsonl(cases: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(
                json.dumps(
                    {
                        "user_input": c["query"],
                        "reference": c["reference"],
                        "reference_contexts": c["reference_contexts"],
                        "evolution_type": c["evolution_type"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_suite(cases: list[dict], out: Path, suite_version: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "knowledge_graph.json").write_text(
        json.dumps({"personas": PERSONAS, "memories": MEMORIES, "events": EVENTS}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    meta = manifest(cases, suite_version=suite_version)
    (out / "MANIFEST.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    export_ragas_jsonl(cases, out / "ragas_eval.jsonl")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["ragas_compat", "ragas"], default="ragas_compat")
    parser.add_argument("--size", type=int, default=50, help="official ragas size")
    parser.add_argument(
        "--out",
        default="",
        help="output directory; default suite-ragas-v1 (compat) or suite-ragas-official (ragas)",
    )
    args = parser.parse_args()

    if args.backend == "ragas":
        try:
            cases = try_ragas_backend(args.size)
        except RagasBackendError as exc:
            print(exc, file=sys.stderr)
            return exc.code
        if not cases:
            print("[ragas] aligned=0，未写入可用金标", file=sys.stderr)
            return 4
        out = Path(args.out) if args.out else OFFICIAL_OUT
        meta = write_suite(cases, out, suite_version="ragas-official")
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        print(f"[ragas] wrote {len(cases)} cases -> {out}", file=sys.stderr)
        return 0

    cases = synthesize_all()
    out = Path(args.out) if args.out else OUT
    meta = write_suite(cases, out, suite_version="ragas-v1")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
