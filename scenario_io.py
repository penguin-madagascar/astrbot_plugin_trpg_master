from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from .memory import apply_knowledge_patches
    from .models import GameSession, ScenarioScript, utc_now_iso
    from .preset_commands import split_list_value
except ImportError:  # pragma: no cover - direct module loading outside package.
    from memory import apply_knowledge_patches
    from models import GameSession, ScenarioScript, utc_now_iso
    from preset_commands import split_list_value


def scenario_history_summary(script: ScenarioScript) -> str:
    parts = [
        f"剧本简介：{script.summary}" if script.summary else "",
        f"剧本背景：{script.background}" if script.background else "",
        f"GM 备注：{script.gm_notes}" if script.gm_notes else "",
    ]
    return "\n".join(part for part in parts if part)


def initialize_scenario_knowledge(
    session: GameSession,
    script: ScenarioScript,
) -> None:
    patches: list[dict[str, Any]] = []
    if script.summary:
        patches.append(
            {
                "op": "add_fact",
                "text": script.summary,
                "visibility": "public",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.background:
        patches.append(
            {
                "op": "add_fact",
                "text": script.background,
                "visibility": "gm_only",
                "importance": 4,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.gm_notes:
        patches.append(
            {
                "op": "add_fact",
                "text": script.gm_notes,
                "visibility": "gm_only",
                "importance": 5,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.opening_scene:
        patches.append(
            {
                "op": "add_timeline_event",
                "summary": f"剧本开场：{script.opening_scene}",
                "visibility": "public",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    for index, hook in enumerate(script.hooks, start=1):
        patches.append(
            {
                "op": "update_clue",
                "clue_id": f"hook-{index}",
                "title": hook,
                "detail": hook,
                "clue_status": "available",
                "visibility": "private",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    apply_knowledge_patches(session, patches)


def script_list_payload(scripts: dict[str, ScenarioScript]) -> list[dict[str, Any]]:
    return [
        script.to_dict()
        for script in sorted(scripts.values(), key=lambda item: item.title)
    ]


def knowledge_entries_payload(sessions: list[GameSession]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for session in sessions:
        knowledge = session.campaign_knowledge
        base = {
            "session_id": session.session_id,
            "session_title": session.title,
        }
        entries.extend(
            {
                **base,
                "type": "timeline",
                "id": entry.event_id,
                "title": f"T{entry.turn}",
                "summary": entry.summary,
                "visibility": entry.visibility,
                "status": entry.status,
                "importance": entry.importance,
            }
            for entry in knowledge.timeline
        )
        entries.extend(
            {
                **base,
                "type": "entity",
                "id": entity.entity_id,
                "title": entity.name,
                "summary": entity.summary,
                "visibility": entity.visibility,
                "status": entity.status,
                "importance": entity.importance,
            }
            for entity in knowledge.entities.values()
        )
        entries.extend(
            {
                **base,
                "type": "fact",
                "id": fact.fact_id,
                "title": fact.text,
                "summary": fact.text,
                "visibility": fact.visibility,
                "status": fact.status,
                "importance": fact.importance,
            }
            for fact in knowledge.facts
        )
        entries.extend(
            {
                **base,
                "type": "clue",
                "id": clue.clue_id,
                "title": clue.title,
                "summary": clue.detail,
                "visibility": clue.visibility,
                "status": clue.status,
                "importance": clue.importance,
            }
            for clue in knowledge.clues.values()
        )
        entries.extend(
            {
                **base,
                "type": "thread",
                "id": thread.thread_id,
                "title": thread.title,
                "summary": thread.summary,
                "visibility": thread.visibility,
                "status": thread.status,
                "importance": thread.importance,
            }
            for thread in knowledge.threads.values()
        )
        entries.extend(
            {
                **base,
                "type": "relationship",
                "id": relationship.relationship_id,
                "title": f"{relationship.source} -> {relationship.target}",
                "summary": relationship.description,
                "visibility": relationship.visibility,
                "status": relationship.status,
                "importance": relationship.importance,
            }
            for relationship in knowledge.relationships
        )
    return entries


def parse_scenario_import(content: str, filename: str = "") -> list[ScenarioScript]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("导入内容不能为空。")
    if filename.lower().endswith(".json") or text[0] in "[{":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            if filename.lower().endswith(".json"):
                raise ValueError("JSON 剧本格式无法解析。") from exc
            return [_parse_markdown_scenario(text)]
        if isinstance(payload, dict) and isinstance(payload.get("scripts"), list):
            payload = payload["scripts"]
        if isinstance(payload, list):
            return [ScenarioScript.from_dict(item) for item in payload]
        if isinstance(payload, dict):
            return [ScenarioScript.from_dict(payload)]
        raise ValueError("JSON 剧本必须是对象、对象数组或包含 scripts 数组的对象。")
    return [_parse_markdown_scenario(text)]


def coerce_config_updates(
    schema: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key, definition in schema.items():
        if key not in payload:
            continue
        field_type = str((definition or {}).get("type") or "string")
        value = payload[key]
        if field_type in {"string", "text"}:
            updates[key] = str(value)
        elif field_type == "int":
            try:
                updates[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be an integer") from exc
        elif field_type == "bool":
            updates[key] = coerce_bool(value)
        else:
            updates[key] = value
    return updates


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value)


def load_config_schema() -> dict[str, Any]:
    path = Path(__file__).with_name("_conf_schema.json")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def current_timestamp() -> str:
    return utc_now_iso()


def _parse_markdown_scenario(markdown: str) -> ScenarioScript:
    title = ""
    sections: dict[str, list[str]] = {}
    current = "gm_notes"
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            heading_text = heading.group(2).strip()
            if heading.group(1) == "#" and not title:
                title = heading_text
                continue
            current = _markdown_section_key(heading_text)
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    if not title:
        title = "导入剧本"
    hooks = _markdown_list_items("\n".join(sections.get("hooks", [])))
    tags = split_list_value(_section_text(sections, "tags"))
    gm_notes = _section_text(sections, "gm_notes")
    unknown = _section_text(sections, "unknown")
    if unknown:
        gm_notes = "\n\n".join(part for part in (gm_notes, unknown) if part)
    return ScenarioScript(
        script_id="",
        title=title,
        language=_section_text(sections, "language") or "zh",
        play_mode=_section_text(sections, "play_mode") or "advanced",
        theme=_section_text(sections, "theme") or title,
        summary=_section_text(sections, "summary"),
        background=_section_text(sections, "background"),
        opening_scene=_section_text(sections, "opening_scene"),
        hooks=hooks,
        gm_notes=gm_notes,
        tags=tags,
        turn_order_mode=_section_text(sections, "turn_order_mode") or "llm_gm",
        ruleset_id=_section_text(sections, "ruleset_id") or "d20_lite",
        rule_nodes=_parse_markdown_rule_nodes(_section_text(sections, "rule_nodes")),
        feature_flags=_parse_markdown_feature_flags(
            _section_text(sections, "feature_flags")
        ),
    )


def _markdown_section_key(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    mapping = {
        "简介": "summary",
        "summary": "summary",
        "背景": "background",
        "background": "background",
        "开场": "opening_scene",
        "开场场景": "opening_scene",
        "opening": "opening_scene",
        "opening scene": "opening_scene",
        "opening_scene": "opening_scene",
        "线索": "hooks",
        "钩子": "hooks",
        "hooks": "hooks",
        "主题": "theme",
        "theme": "theme",
        "语言": "language",
        "language": "language",
        "模式": "play_mode",
        "玩法模式": "play_mode",
        "play_mode": "play_mode",
        "play mode": "play_mode",
        "mode": "play_mode",
        "标签": "tags",
        "tags": "tags",
        "行动顺序": "turn_order_mode",
        "行动顺序模式": "turn_order_mode",
        "turn_order_mode": "turn_order_mode",
        "turn order": "turn_order_mode",
        "turn mode": "turn_order_mode",
        "规则": "ruleset_id",
        "规则系统": "ruleset_id",
        "ruleset": "ruleset_id",
        "ruleset_id": "ruleset_id",
        "rule set": "ruleset_id",
        "检定节点": "rule_nodes",
        "规则节点": "rule_nodes",
        "rule_nodes": "rule_nodes",
        "rule nodes": "rule_nodes",
        "checks": "rule_nodes",
        "机制开关": "feature_flags",
        "功能开关": "feature_flags",
        "feature_flags": "feature_flags",
        "feature flags": "feature_flags",
        "features": "feature_flags",
        "gm 备注": "gm_notes",
        "gm备注": "gm_notes",
        "gm notes": "gm_notes",
        "notes": "gm_notes",
        "备注": "gm_notes",
    }
    return mapping.get(normalized, "unknown")


def _section_text(sections: dict[str, list[str]], key: str) -> str:
    lines = sections.get(key, [])
    return "\n".join(line.strip() for line in lines).strip()


def _markdown_list_items(value: str) -> list[str]:
    items = []
    for line in value.splitlines():
        item = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
        if item:
            items.append(item)
    return items


def _parse_markdown_rule_nodes(value: str) -> list[dict[str, Any]]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _parse_markdown_feature_flags(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
