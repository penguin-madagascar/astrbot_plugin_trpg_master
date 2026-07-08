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
