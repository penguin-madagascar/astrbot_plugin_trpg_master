from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .models import (
        GameSession,
        PlayerCharacter,
        TurnOrderState,
        normalize_turn_order_mode,
        normalize_turn_order_phase,
    )
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import (
        GameSession,
        PlayerCharacter,
        TurnOrderState,
        normalize_turn_order_mode,
        normalize_turn_order_phase,
    )


@dataclass(frozen=True)
class TurnControlApplyResult:
    applied: bool
    op: str
    message: str


def initialize_turn_order(
    session: GameSession,
    *,
    enabled: bool,
    mode: str = "soft",
) -> None:
    normalized_mode = normalize_turn_order_mode(mode)
    session.turn_order = TurnOrderState(
        enabled=enabled,
        mode=normalized_mode,
        phase=normalize_turn_order_phase("", normalized_mode),
    )


def add_player_to_turn_order(session: GameSession, user_id: str) -> None:
    order = session.turn_order
    if not order.enabled:
        return
    normalized_user_id = str(user_id or "")
    if normalized_user_id not in session.players:
        return
    normalize_turn_order(session)
    if normalized_user_id not in order.queue:
        order.queue.append(normalized_user_id)
    normalize_turn_order(session)


def normalize_turn_order(session: GameSession) -> None:
    order = session.turn_order
    seen: set[str] = set()
    order.queue = [
        user_id
        for user_id in (str(item) for item in order.queue)
        if user_id in session.players and not (user_id in seen or seen.add(user_id))
    ]
    if not order.queue:
        order.current_index = 0
        return
    if order.current_index >= len(order.queue):
        order.current_index = len(order.queue) - 1
    order.current_index = max(0, order.current_index)
    order.round_count = max(1, order.round_count)


def current_turn_user_id(session: GameSession) -> str:
    normalize_turn_order(session)
    order = session.turn_order
    if not order.enabled or not order.queue:
        return ""
    return order.queue[order.current_index]


def current_turn_player(session: GameSession) -> PlayerCharacter | None:
    user_id = current_turn_user_id(session)
    return session.players.get(user_id) if user_id else None


def advance_turn_order(session: GameSession) -> PlayerCharacter | None:
    normalize_turn_order(session)
    order = session.turn_order
    if not order.enabled or not order.queue:
        return None
    order.current_index += 1
    if order.current_index >= len(order.queue):
        order.current_index = 0
        order.round_count += 1
    return current_turn_player(session)


def is_turn_order_active(session: GameSession) -> bool:
    normalize_turn_order(session)
    order = session.turn_order
    if not (order.enabled and not order.paused and order.queue):
        return False
    return order.mode == "soft" or order.phase == "turn_order"


def is_current_turn(session: GameSession, user_id: str) -> bool:
    return bool(user_id and current_turn_user_id(session) == str(user_id))


def can_finish_turn(session: GameSession, user_id: str) -> bool:
    return session.turn_order.mode == "soft" and is_current_turn(session, user_id)


def can_submit_action(session: GameSession, user_id: str) -> bool:
    order = session.turn_order
    if not is_turn_order_active(session):
        return True
    if order.mode == "llm_gm" and order.phase == "turn_order":
        return is_current_turn(session, user_id)
    return True


def apply_turn_controls(
    session: GameSession,
    controls: list[dict[str, Any]],
) -> list[TurnControlApplyResult]:
    results: list[TurnControlApplyResult] = []
    order = session.turn_order
    if not order.enabled or order.mode != "llm_gm":
        return results

    for control in controls or []:
        op = str(control.get("op") or "").strip().lower()
        if op == "set_phase":
            phase = normalize_turn_order_phase(control.get("phase"), order.mode)
            order.phase = phase
            order.paused = phase == "paused"
            results.append(_applied(op, f"phase={order.phase}"))
            continue
        if op == "set_queue":
            actors = _control_actor_list(control)
            user_ids, missing = _actor_user_ids(session, actors)
            if not user_ids:
                results.append(_skipped(op, f"unknown actors: {', '.join(missing) or '-'}"))
                continue
            order.queue = user_ids
            order.current_index = 0
            normalize_turn_order(session)
            message = "queue=" + ", ".join(_player_label(session, item) for item in order.queue)
            if missing:
                message += f"; skipped unknown: {', '.join(missing)}"
            results.append(_applied(op, message))
            continue
        if op == "set_current":
            actor = str(control.get("actor") or "").strip()
            user_id = _actor_user_id(session, actor)
            if not user_id:
                results.append(_skipped(op, f"unknown actor: {actor or '-'}"))
                continue
            normalize_turn_order(session)
            if user_id not in order.queue:
                order.queue.append(user_id)
            order.current_index = order.queue.index(user_id)
            order.phase = "turn_order"
            order.paused = False
            results.append(_applied(op, f"current={_player_label(session, user_id)}"))
            continue
        if op == "advance":
            player = advance_turn_order(session)
            if player is None:
                results.append(_skipped(op, "queue is empty"))
                continue
            order.phase = "turn_order"
            order.paused = False
            results.append(_applied(op, f"current={player.character_name}"))
            continue
        if op == "pause":
            order.phase = "paused"
            order.paused = True
            results.append(_applied(op, "paused"))
            continue
        if op == "resume":
            order.paused = False
            order.phase = "turn_order" if order.queue else "free"
            results.append(_applied(op, f"phase={order.phase}"))
            continue
        if op == "control_note":
            note = str(control.get("text") or control.get("note") or control.get("reason") or "").strip()
            if not note:
                results.append(_skipped(op, "empty note"))
                continue
            order.control_note = note
            results.append(_applied(op, note))
            continue
        results.append(_skipped(op or "-", "unsupported op"))
    return results


def _control_actor_list(control: dict[str, Any]) -> list[str]:
    value = control.get("actors", control.get("queue", []))
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _actor_user_ids(
    session: GameSession,
    actors: list[str],
) -> tuple[list[str], list[str]]:
    user_ids: list[str] = []
    missing: list[str] = []
    for actor in actors:
        user_id = _actor_user_id(session, actor)
        if not user_id:
            missing.append(actor)
            continue
        if user_id not in user_ids:
            user_ids.append(user_id)
    return user_ids, missing


def _actor_user_id(session: GameSession, actor: str) -> str:
    normalized = str(actor or "").strip()
    if not normalized:
        return ""
    if normalized in session.players:
        return normalized
    for user_id, player in session.players.items():
        if player.character_name == normalized or player.display_name == normalized:
            return user_id
    return ""


def _player_label(session: GameSession, user_id: str) -> str:
    player = session.players.get(user_id)
    return player.character_name if player else str(user_id)


def _applied(op: str, message: str) -> TurnControlApplyResult:
    return TurnControlApplyResult(applied=True, op=op, message=message)


def _skipped(op: str, message: str) -> TurnControlApplyResult:
    return TurnControlApplyResult(applied=False, op=op, message=message)
