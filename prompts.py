from __future__ import annotations

import json
from typing import Any

try:
    from .models import GameSession
except ImportError:  # pragma: no cover - direct import outside package.
    from models import GameSession


LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}

DEFAULT_GM_SYSTEM_PROMPT = """
你是 TRPG GM/KP。你要推动故事、扮演 NPC、描述环境和行动后果。
你不能直接决定骰子结果；遇到有风险、不确定或对抗的行动，必须提出 dice_request。
你不能直接伪造角色 HP/SAN/物品/状态变化，只能提出 state_patches，由系统校验。
回复必须包含面向玩家的叙事文本，以及一个 JSON fenced block。
叙事不要过长，每回合 150-350 字，最后给出 1-3 个开放线索，但不要限制玩家只能选择这些线索。
JSON 的 key 必须保持英文，方便 Python 解析。除 JSON key 外，叙事、NPC 台词、reason、memory_notes、plot_threads 都应使用本次 session 的输出语言。
不要把骰子结果写死，不要擅自改角色状态。
如果玩家行动明显安全、无风险、无对抗，可以不请求骰子。
如果玩家行动存在风险、不确定性或对抗，必须请求 dice_request。
""".strip()


PATCH_SCHEMA = {
    "dice_requests": [
        {
            "id": "check1",
            "type": "skill_check",
            "actor": "角色名",
            "skill": "DEX",
            "dc": 12,
            "reason": "躲避落石",
        }
    ],
    "state_patches": [
        {
            "target": "pc:角色名",
            "op": "hp_delta",
            "value": -1,
            "reason": "碎石擦伤",
        }
    ],
    "scene_patch": {"location": "...", "description": "..."},
    "new_plot_threads": [],
    "memory_notes": [],
}


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get(language, LANGUAGE_NAMES["zh"])


def session_snapshot(session: GameSession) -> dict[str, Any]:
    return {
        "title": session.title,
        "theme": session.theme,
        "language": session.language,
        "status": session.status,
        "turn_count": session.turn_count,
        "scene": session.scene,
        "players": {
            player.character_name: {
                "user_id": player.user_id,
                "display_name": player.display_name,
                "concept": player.concept,
                "hp": player.hp,
                "san": player.san,
                "attributes": player.attributes,
                "skills": player.skills,
                "inventory": player.inventory,
                "status_effects": player.status_effects,
            }
            for player in session.players.values()
        },
        "npcs": {name: npc.to_dict() for name, npc in session.npcs.items()},
        "plot_threads": session.plot_threads,
        "global_items": session.global_items,
        "history_summary": session.history_summary,
        "recent_events": session.recent_events,
        "scenario_script": session.scenario_script,
    }


def build_opening_prompt(session: GameSession) -> str:
    language = language_name(session.language)
    scenario = _format_scenario_context(session.scenario_script)
    scenario_part = f"\n剧本资料：\n{scenario}\n" if scenario else ""
    return (
        f"本次 session 的输出语言是 {language}。\n"
        f"主题：{session.theme}\n"
        f"{scenario_part}"
        "请生成跑团开场，只输出面向玩家的叙事文本，不要输出 JSON。\n"
        "需要包含当前场景、主要威胁、可行动线索。不要给出固定选项，不要替玩家做决定。"
    )


def build_action_prompt(session: GameSession, actor: str, action: str) -> str:
    language = language_name(session.language)
    snapshot = json.dumps(session_snapshot(session), ensure_ascii=False, indent=2)
    schema = json.dumps(PATCH_SCHEMA, ensure_ascii=False, indent=2)
    return (
        f"当前 session 的输出语言是 {language}。\n"
        "除 JSON key 外，叙事、NPC 台词、reason、memory_notes、plot_threads 都必须使用该语言。\n"
        "JSON key 必须保持英文。\n"
        "不要写死骰子结果。不要直接修改角色状态，只能提出 state_patches。\n"
        "当前 session 快照：\n"
        f"{snapshot}\n\n"
        f"行动玩家：{actor}\n"
        f"玩家行动：{action}\n\n"
        "请先输出面向玩家的叙事文本，然后输出一个 ```json fenced block。"
        "JSON 格式必须符合以下结构，字段缺省时使用空数组或空对象：\n"
        f"```json\n{schema}\n```"
    )


def build_resolution_prompt(
    session: GameSession,
    narrative: str,
    dice_summary: str,
    state_summary: str,
) -> str:
    language = language_name(session.language)
    return (
        f"当前 session 的输出语言是 {language}。\n"
        "系统已经完成真实掷骰和状态校验。请只基于这些结果补充 1 段简短结算叙事，"
        "不要输出 JSON，不要新增骰子或状态变化。\n\n"
        f"原叙事：\n{narrative}\n\n"
        f"骰子结果：\n{dice_summary}\n\n"
        f"状态应用结果：\n{state_summary}"
    )


def build_summary_prompt(session: GameSession) -> str:
    language = language_name(session.language)
    events = "\n".join(f"- {event}" for event in session.recent_events)
    return (
        f"当前 session 的输出语言是 {language}。\n"
        "请把以下近期事件压缩进一段可供后续 GM 使用的剧情摘要。"
        "只返回摘要文本，不要输出 JSON。\n\n"
        f"既有摘要：\n{session.history_summary or '(empty)'}\n\n"
        f"近期事件：\n{events}"
    )


def _format_scenario_context(scenario: dict[str, Any] | None) -> str:
    if not scenario:
        return ""
    lines = []
    labels = [
        ("title", "标题"),
        ("summary", "简介"),
        ("background", "背景"),
        ("opening_scene", "开场场景"),
        ("gm_notes", "GM 备注"),
    ]
    for key, label in labels:
        value = str(scenario.get(key) or "").strip()
        if value:
            lines.append(f"{label}：{value}")
    hooks = [str(item) for item in scenario.get("hooks", []) if str(item).strip()]
    if hooks:
        lines.append("线索：\n" + "\n".join(f"- {hook}" for hook in hooks))
    tags = [str(item) for item in scenario.get("tags", []) if str(item).strip()]
    if tags:
        lines.append(f"标签：{', '.join(tags)}")
    return "\n".join(lines)
