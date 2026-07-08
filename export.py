from __future__ import annotations

import re
from pathlib import Path

try:
    from .models import GameSession
except ImportError:  # pragma: no cover - direct import outside package.
    from models import GameSession


LABELS = {
    "zh": {
        "theme": "主题",
        "language": "语言",
        "players": "玩家角色",
        "summary": "剧情摘要",
        "logs": "逐回合记录",
        "scene": "当前场景",
    },
    "en": {
        "theme": "Theme",
        "language": "Language",
        "players": "Player Characters",
        "summary": "Story Summary",
        "logs": "Session Log",
        "scene": "Current Scene",
    },
    "ja": {
        "theme": "テーマ",
        "language": "言語",
        "players": "プレイヤーキャラクター",
        "summary": "物語の要約",
        "logs": "セッションログ",
        "scene": "現在のシーン",
    },
    "ko": {
        "theme": "테마",
        "language": "언어",
        "players": "플레이어 캐릭터",
        "summary": "이야기 요약",
        "logs": "세션 로그",
        "scene": "현재 장면",
    },
}


def export_session_markdown(session: GameSession, data_dir: Path) -> Path:
    exports_dir = Path(data_dir) / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_filename(session.title)}-{session.turn_count}.md"
    path = exports_dir / filename
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write(format_session_markdown(session))
        file.write("\n")
    return path


def format_session_markdown(session: GameSession) -> str:
    labels = LABELS.get(session.language, LABELS["zh"])
    lines = [
        f"# {session.title}",
        "",
        f"- {labels['theme']}: {session.theme}",
        f"- {labels['language']}: {session.language}",
        f"- Status: {session.status}",
        f"- Turns: {session.turn_count}",
        "",
        f"## {labels['scene']}",
        "",
        str(session.scene.get("description") or session.scene.get("location") or ""),
        "",
        f"## {labels['players']}",
        "",
    ]
    if session.players:
        for pc in session.players.values():
            lines.append(
                f"- **{pc.character_name}** ({pc.display_name}): "
                f"HP {pc.hp}, SAN {pc.san}; {pc.concept}"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", f"## {labels['summary']}", "", session.history_summary or ""])
    if session.recent_events:
        lines.extend(["", "### Recent Events", ""])
        lines.extend(f"- {event}" for event in session.recent_events)

    _append_campaign_knowledge(lines, session)

    lines.extend(["", f"## {labels['logs']}", ""])
    for entry in session.logs:
        lines.extend(
            [
                f"### {entry.timestamp} - {entry.command}",
                "",
                f"- User: {entry.user}",
                f"- Input: {entry.input}",
                f"- Output: {entry.output_summary}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", value).strip("_")
    return cleaned[:80] or "trpg_session"


def _append_campaign_knowledge(lines: list[str], session: GameSession) -> None:
    knowledge = session.campaign_knowledge
    if knowledge.timeline:
        lines.extend(["", "## 战役时间线", ""])
        lines.extend(
            f"- T{entry.turn} [{entry.visibility}/{entry.importance}]: {entry.summary}"
            for entry in knowledge.timeline
            if entry.status != "obsolete"
        )
    if knowledge.entities:
        lines.extend(["", "## 战役实体", ""])
        for entity in knowledge.entities.values():
            aliases = f" aliases={', '.join(entity.aliases)}" if entity.aliases else ""
            lines.append(
                f"- **{entity.name}** ({entity.kind}, {entity.visibility}/{entity.importance})"
                f"{aliases}: {entity.summary}"
            )
    if knowledge.facts:
        lines.extend(["", "## 战役事实", ""])
        lines.extend(
            f"- [{fact.visibility}/{fact.importance}] {fact.text}"
            for fact in knowledge.facts
            if fact.status != "obsolete"
        )
    if knowledge.clues:
        lines.extend(["", "## 线索", ""])
        for clue in knowledge.clues.values():
            if clue.status == "obsolete":
                continue
            lines.append(
                f"- **{clue.title}** [{clue.clue_status}, {clue.visibility}/{clue.importance}]: "
                f"{clue.detail}"
            )
    if knowledge.threads:
        lines.extend(["", "## 剧情线", ""])
        for thread in knowledge.threads.values():
            if thread.status == "obsolete":
                continue
            lines.append(
                f"- **{thread.title}** [{thread.thread_status}, {thread.visibility}/{thread.importance}]: "
                f"{thread.summary}"
            )
    if knowledge.relationships:
        lines.extend(["", "## 关系", ""])
        lines.extend(
            f"- {relationship.source} -> {relationship.target} "
            f"[{relationship.visibility}/{relationship.importance}]: {relationship.description}"
            for relationship in knowledge.relationships
            if relationship.status != "obsolete"
        )
    if knowledge.archive_summary:
        lines.extend(["", "## 归档摘要", "", knowledge.archive_summary])
