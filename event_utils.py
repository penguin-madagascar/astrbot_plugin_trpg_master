from __future__ import annotations

from typing import Any

try:
    from . import scenario_io
    from .models import normalize_play_mode
except ImportError:  # pragma: no cover - direct module loading outside package.
    import scenario_io
    from models import normalize_play_mode


def session_id(event: Any) -> str:
    return str(
        getattr(event, "unified_msg_origin", "")
        or getattr(event, "session_id", "")
        or "default"
    )


def sender_id(event: Any) -> str:
    getter = getattr(event, "get_sender_id", None)
    value = getter() if callable(getter) else getattr(event, "sender_id", "")
    return str(value or "unknown")


def sender_name(event: Any) -> str:
    getter = getattr(event, "get_sender_name", None)
    value = getter() if callable(getter) else getattr(event, "sender_name", "")
    return str(value or sender_id(event))


def sender_label(event: Any) -> str:
    return f"{sender_name(event)}({sender_id(event)})"


def event_message_text(event: Any) -> str:
    getter = getattr(event, "get_message_str", None)
    value = getter() if callable(getter) else getattr(event, "message_str", "")
    return str(value or "")


def block_default_llm(event: Any) -> None:
    blocker = getattr(event, "should_call_llm", None)
    if callable(blocker):
        blocker(True)
        return
    setattr(event, "call_llm", True)


def stop_event(event: Any) -> None:
    stopper = getattr(event, "stop_event", None)
    if callable(stopper):
        stopper()


def split_first(value: str) -> tuple[str, str]:
    parts = value.split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def split_start_mode(value: str) -> tuple[str, str]:
    first, rest = split_first(str(value or "").strip())
    mode = normalize_play_mode(first, default="")
    if mode:
        return mode, rest.strip()
    return "", str(value or "").strip()


def one_line(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit]


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def config_bool(config: dict, key: str, default: bool) -> bool:
    if key not in config:
        return default
    return scenario_io.coerce_bool(config.get(key))
