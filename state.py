from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

try:
    from astrbot.api import logger
except ModuleNotFoundError:  # pragma: no cover - unit tests outside AstrBot.
    logger = logging.getLogger(__name__)

try:
    from .models import GameSession, PlayerCharacter
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import GameSession, PlayerCharacter


ALLOWED_PATCH_OPS = {
    "hp_delta",
    "san_delta",
    "add_item",
    "remove_item",
    "add_status",
    "remove_status",
}


@dataclass(frozen=True)
class PatchApplyResult:
    applied: bool
    target: str
    op: str
    message: str


def apply_state_patches(
    session: GameSession,
    patches: list[dict[str, Any]],
) -> list[PatchApplyResult]:
    results: list[PatchApplyResult] = []
    for patch in patches or []:
        target = str(patch.get("target", ""))
        op = str(patch.get("op", ""))
        value = patch.get("value")

        if not target.startswith("pc:"):
            results.append(_skip(target, op, "unsupported target"))
            continue
        if op not in ALLOWED_PATCH_OPS:
            results.append(_skip(target, op, "unsupported op"))
            continue

        pc = session.player_by_character_name(target[3:])
        if pc is None:
            logger.warning("TRPG state patch skipped: PC not found: %s", target)
            results.append(_skip(target, op, "pc not found"))
            continue

        result = _apply_patch_to_pc(pc, target, op, value)
        results.append(result)
    return results


def _apply_patch_to_pc(
    pc: PlayerCharacter,
    target: str,
    op: str,
    value: Any,
) -> PatchApplyResult:
    if op in {"hp_delta", "san_delta"}:
        try:
            delta = int(value)
        except (TypeError, ValueError):
            return _skip(target, op, "invalid integer")
        if op == "hp_delta":
            before = pc.hp
            pc.hp = max(0, pc.hp + delta)
            return _applied(target, op, f"{pc.character_name} HP {before}->{pc.hp}")
        before = pc.san
        pc.san = max(0, pc.san + delta)
        return _applied(target, op, f"{pc.character_name} SAN {before}->{pc.san}")

    text = str(value).strip()
    if not text:
        return _skip(target, op, "empty value")

    if op == "add_item":
        if text not in pc.inventory:
            pc.inventory.append(text)
        return _applied(target, op, f"{pc.character_name} gained item: {text}")
    if op == "remove_item":
        if text in pc.inventory:
            pc.inventory.remove(text)
        return _applied(target, op, f"{pc.character_name} removed item: {text}")
    if op == "add_status":
        if text not in pc.status_effects:
            pc.status_effects.append(text)
        return _applied(target, op, f"{pc.character_name} gained status: {text}")
    if op == "remove_status":
        if text in pc.status_effects:
            pc.status_effects.remove(text)
        return _applied(target, op, f"{pc.character_name} removed status: {text}")

    return _skip(target, op, "unsupported op")


def _applied(target: str, op: str, message: str) -> PatchApplyResult:
    return PatchApplyResult(applied=True, target=target, op=op, message=message)


def _skip(target: str, op: str, reason: str) -> PatchApplyResult:
    logger.warning("TRPG state patch skipped: %s target=%s op=%s", reason, target, op)
    return PatchApplyResult(applied=False, target=target, op=op, message=reason)
