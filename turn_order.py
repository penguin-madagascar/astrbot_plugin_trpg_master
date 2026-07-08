from __future__ import annotations

try:
    from .models import GameSession, PlayerCharacter, TurnOrderState
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import GameSession, PlayerCharacter, TurnOrderState


def initialize_turn_order(
    session: GameSession,
    *,
    enabled: bool,
    gm_user_id: str,
    gm_display_name: str,
) -> None:
    session.turn_order = TurnOrderState(
        enabled=enabled,
        gm_user_id=gm_user_id,
        gm_display_name=gm_display_name,
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


def resolve_turn_user_id(session: GameSession, query: str) -> str:
    target = str(query or "").strip()
    if not target:
        return ""
    if target in session.players:
        return target
    for user_id, player in session.players.items():
        if player.character_name == target or player.display_name == target:
            return user_id
    return ""


def set_current_turn(session: GameSession, query: str) -> PlayerCharacter | None:
    user_id = resolve_turn_user_id(session, query)
    if not user_id:
        return None
    order = session.turn_order
    if user_id not in order.queue:
        order.queue.append(user_id)
    normalize_turn_order(session)
    order.current_index = order.queue.index(user_id)
    return session.players[user_id]


def is_turn_order_active(session: GameSession) -> bool:
    normalize_turn_order(session)
    order = session.turn_order
    return bool(order.enabled and not order.paused and order.queue)


def is_current_turn(session: GameSession, user_id: str) -> bool:
    return bool(user_id and current_turn_user_id(session) == str(user_id))


def can_manage_turn_order(
    session: GameSession,
    user_id: str,
    *,
    requires_gm: bool,
) -> bool:
    return not requires_gm or str(user_id or "") == session.turn_order.gm_user_id


def can_finish_turn(
    session: GameSession,
    user_id: str,
    *,
    requires_gm: bool,
) -> bool:
    return is_current_turn(session, user_id) or can_manage_turn_order(
        session,
        user_id,
        requires_gm=requires_gm,
    )
