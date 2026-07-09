from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from . import dice
    from .models import GameSession, PlayerCharacter
except ImportError:  # pragma: no cover - direct import outside package.
    import dice
    from models import GameSession, PlayerCharacter


DEFAULT_RULESET_ID = "d20_lite"
SUPPORTED_RULESET_IDS = {"d20_lite", "coc7_lite"}


@dataclass(frozen=True)
class CheckRequest:
    type: str = "skill_check"
    actor: str = ""
    stat: str = ""
    skill: str = ""
    dc: int | None = None
    difficulty: str = ""
    advantage: str = ""
    bonus_dice: int = 0
    penalty_dice: int = 0
    opponent: str = ""
    script_check_id: str = ""
    reason: str = ""
    success_loss: str = "0"
    failure_loss: str = "0"

    @classmethod
    def from_payload(cls, payload: "CheckRequest | dict[str, Any]") -> "CheckRequest":
        if isinstance(payload, CheckRequest):
            return payload
        data = dict(payload or {})
        return cls(
            type=str(data.get("type") or "skill_check"),
            actor=str(data.get("actor") or ""),
            stat=str(data.get("stat") or ""),
            skill=str(data.get("skill") or ""),
            dc=_optional_int(data.get("dc")),
            difficulty=str(data.get("difficulty") or ""),
            advantage=str(data.get("advantage") or ""),
            bonus_dice=_safe_int(data.get("bonus_dice"), 0),
            penalty_dice=_safe_int(data.get("penalty_dice"), 0),
            opponent=str(data.get("opponent") or ""),
            script_check_id=str(data.get("script_check_id") or ""),
            reason=str(data.get("reason") or ""),
            success_loss=str(data.get("success_loss") or "0"),
            failure_loss=str(data.get("failure_loss") or "0"),
        )


@dataclass(frozen=True)
class CheckResult:
    applied: bool
    ruleset_id: str
    type: str
    actor: str
    success: bool = False
    message: str = ""
    rolls: list[int] = field(default_factory=list)
    total: int | None = None
    target: int | None = None
    dc: int | None = None
    success_level: str = ""
    opponent_total: int | None = None
    state_patches: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RulesetStatePatchResult:
    applied: bool
    target: str
    op: str
    message: str


@dataclass(frozen=True)
class Ruleset:
    ruleset_id: str
    name: str
    summary: str
    check_types: tuple[str, ...]

    def resolve_check(
        self,
        session: GameSession,
        request: CheckRequest,
    ) -> CheckResult:
        if self.ruleset_id == "coc7_lite":
            return _resolve_coc7_check(session, request)
        return _resolve_d20_check(session, request)

    def format_character(self, pc: PlayerCharacter) -> str:
        if self.ruleset_id == "coc7_lite":
            return _format_coc7_character(pc)
        return _format_d20_character(pc)


RULESETS = {
    "d20_lite": Ruleset(
        ruleset_id="d20_lite",
        name="d20 Lite",
        summary="d20 属性/技能检定、优势/劣势、对抗、基础伤害与治疗。",
        check_types=("skill_check", "attribute_check", "saving_throw", "opposed_check"),
    ),
    "coc7_lite": Ruleset(
        ruleset_id="coc7_lite",
        name="CoC 7e Lite",
        summary="d100 技能/属性检定、成功等级、奖励/惩罚骰和 SAN 检定。",
        check_types=("skill_check", "attribute_check", "san_check"),
    ),
}


def normalize_ruleset_id(value: Any, default: str = DEFAULT_RULESET_ID) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_RULESET_IDS:
        return normalized
    return default if default in SUPPORTED_RULESET_IDS else DEFAULT_RULESET_ID


def list_rulesets() -> list[Ruleset]:
    return [RULESETS[key] for key in sorted(RULESETS)]


def get_ruleset(ruleset_id: Any) -> Ruleset:
    return RULESETS[normalize_ruleset_id(ruleset_id)]


def resolve_check_request(
    session: GameSession,
    payload: CheckRequest | dict[str, Any],
) -> CheckResult:
    request = CheckRequest.from_payload(payload)
    return get_ruleset(getattr(session, "ruleset_id", DEFAULT_RULESET_ID)).resolve_check(
        session,
        request,
    )


def apply_ruleset_state_patch(
    session: GameSession,
    patch: dict[str, Any],
) -> RulesetStatePatchResult:
    target = str(patch.get("target") or "")
    op = str(patch.get("op") or "")
    field_name = str(patch.get("field") or patch.get("resource") or "").strip()
    pc = _pc_from_target(session, target)
    if pc is None:
        return RulesetStatePatchResult(False, target, op, "pc not found")

    if op in {"damage", "heal"}:
        amount = _safe_int(patch.get("value"), 0)
        before = pc.hp
        pc.hp = max(0, pc.hp - amount if op == "damage" else pc.hp + amount)
        return RulesetStatePatchResult(
            True,
            target,
            op,
            f"{pc.character_name} HP {before}->{pc.hp}",
        )
    if op == "resource_delta":
        if not field_name:
            return RulesetStatePatchResult(False, target, op, "missing resource field")
        delta = _safe_int(patch.get("value"), 0)
        before = _safe_int(pc.ruleset_data.get(field_name), 0)
        pc.ruleset_data[field_name] = before + delta
        return RulesetStatePatchResult(
            True,
            target,
            op,
            f"{pc.character_name} {field_name} {before}->{pc.ruleset_data[field_name]}",
        )
    if op == "skill_delta":
        if not field_name:
            return RulesetStatePatchResult(False, target, op, "missing skill field")
        delta = _safe_int(patch.get("value"), 0)
        before = _safe_int(pc.skills.get(field_name), 0)
        pc.skills[field_name] = before + delta
        return RulesetStatePatchResult(
            True,
            target,
            op,
            f"{pc.character_name} {field_name} {before}->{pc.skills[field_name]}",
        )

    return RulesetStatePatchResult(False, target, op, "unsupported op")


def _resolve_d20_check(session: GameSession, request: CheckRequest) -> CheckResult:
    pc = session.player_by_character_name(request.actor)
    if pc is None:
        return _skipped("d20_lite", request, "pc not found")
    label, modifier = _d20_modifier(pc, request)
    rolls = _d20_rolls(request.advantage)
    roll = _choose_d20_roll(rolls, request.advantage)
    total = roll + modifier
    opponent_total = None
    dc = request.dc if request.dc is not None else 10
    if request.type == "opposed_check" and request.opponent:
        opponent = session.player_by_character_name(request.opponent)
        opponent_total = 10
        if opponent is not None:
            _opponent_label, opponent_modifier = _d20_modifier(opponent, request)
            opponent_total += opponent_modifier
        dc = opponent_total
    success = total >= dc
    reason = f" ({request.reason})" if request.reason else ""
    opposed = f", opponent={opponent_total}" if opponent_total is not None else ""
    return CheckResult(
        applied=True,
        ruleset_id="d20_lite",
        type=request.type,
        actor=request.actor,
        success=success,
        message=(
            f"{request.actor} {label} vs DC {dc}: rolls={rolls}, "
            f"mod={modifier}, total={total} => "
            f"{'success' if success else 'failure'}{opposed}{reason}"
        ),
        rolls=rolls,
        total=total,
        dc=dc,
        opponent_total=opponent_total,
    )


def _resolve_coc7_check(session: GameSession, request: CheckRequest) -> CheckResult:
    pc = session.player_by_character_name(request.actor)
    if pc is None:
        return _skipped("coc7_lite", request, "pc not found")
    if request.type == "san_check":
        target = pc.san
        label = "SAN"
    else:
        label, target = _coc7_target(pc, request)
    total, rolls = _roll_coc7_d100(request.bonus_dice, request.penalty_dice)
    success_level = _coc7_success_level(total, target)
    success = success_level != "failure"
    state_patches: list[dict[str, Any]] = []
    if request.type == "san_check":
        loss_expr = request.success_loss if success else request.failure_loss
        loss = _roll_loss_expression(loss_expr)
        if loss:
            state_patches.append(
                {
                    "target": f"pc:{pc.character_name}",
                    "op": "san_delta",
                    "value": -loss,
                    "reason": (
                        f"SAN check {'success_loss' if success else 'failure_loss'} "
                        f"{loss_expr}"
                    ),
                }
            )
    reason = f" ({request.reason})" if request.reason else ""
    return CheckResult(
        applied=True,
        ruleset_id="coc7_lite",
        type=request.type,
        actor=request.actor,
        success=success,
        message=(
            f"{request.actor} {label} target {target}: rolls={rolls}, "
            f"total={total} => {success_level} success{reason}"
            if success
            else f"{request.actor} {label} target {target}: rolls={rolls}, "
            f"total={total} => failure{reason}"
        ),
        rolls=rolls,
        total=total,
        target=target,
        success_level=success_level,
        state_patches=state_patches,
    )


def _format_d20_character(pc: PlayerCharacter) -> str:
    attrs = ", ".join(f"{key} {value}" for key, value in pc.attributes.items())
    skills = ", ".join(f"{key} {value}" for key, value in pc.skills.items()) or "-"
    inventory = ", ".join(pc.inventory) if pc.inventory else "-"
    status = ", ".join(pc.status_effects) if pc.status_effects else "-"
    return (
        f"Ruleset: d20_lite\n"
        f"Character: {pc.character_name}\n"
        f"Concept: {pc.concept}\n"
        f"HP: {pc.hp} / SAN: {pc.san}\n"
        f"Attributes: {attrs}\n"
        f"Skills: {skills}\n"
        f"Inventory: {inventory}\n"
        f"Status: {status}"
    )


def _format_coc7_character(pc: PlayerCharacter) -> str:
    attrs = ", ".join(f"{key} {value}" for key, value in pc.attributes.items())
    skills = ", ".join(f"{key} {value}" for key, value in pc.skills.items()) or "-"
    extra = ", ".join(
        f"{key} {value}" for key, value in sorted(pc.ruleset_data.items())
    ) or "-"
    inventory = ", ".join(pc.inventory) if pc.inventory else "-"
    status = ", ".join(pc.status_effects) if pc.status_effects else "-"
    return (
        f"Ruleset: coc7_lite\n"
        f"Investigator: {pc.character_name}\n"
        f"Concept: {pc.concept}\n"
        f"HP: {pc.hp} / SAN: {pc.san}\n"
        f"Attributes: {attrs}\n"
        f"Skills: {skills}\n"
        f"Resources: {extra}\n"
        f"Inventory: {inventory}\n"
        f"Status: {status}"
    )


def _d20_modifier(pc: PlayerCharacter, request: CheckRequest) -> tuple[str, int]:
    label = (request.stat or request.skill or "DEX").strip()
    upper = label.upper()
    if upper in pc.attributes:
        return upper, (int(pc.attributes[upper]) - 10) // 2
    if label in pc.skills:
        return label, int(pc.skills[label])
    return upper or "DEX", 0


def _d20_rolls(advantage: str) -> list[int]:
    normalized = str(advantage or "").strip().lower()
    count = 2 if normalized in {"advantage", "disadvantage"} else 1
    return [dice.secrets.randbelow(20) + 1 for _ in range(count)]


def _choose_d20_roll(rolls: list[int], advantage: str) -> int:
    normalized = str(advantage or "").strip().lower()
    if normalized == "advantage":
        return max(rolls)
    if normalized == "disadvantage":
        return min(rolls)
    return rolls[0]


def _coc7_target(pc: PlayerCharacter, request: CheckRequest) -> tuple[str, int]:
    label = (request.skill or request.stat or "侦查").strip()
    upper = label.upper()
    if label in pc.skills:
        return label, int(pc.skills[label])
    if upper in pc.attributes:
        return upper, int(pc.attributes[upper])
    if label in pc.ruleset_data:
        return label, int(pc.ruleset_data[label])
    return label or "侦查", 1


def _roll_coc7_d100(bonus_dice: int, penalty_dice: int) -> tuple[int, list[int]]:
    units = dice.secrets.randbelow(10)
    base_tens = dice.secrets.randbelow(10)
    candidates = [_compose_coc7_roll(base_tens, units)]
    net = max(-2, min(2, int(bonus_dice) - int(penalty_dice)))
    for _index in range(abs(net)):
        candidates.append(_compose_coc7_roll(dice.secrets.randbelow(10), units))
    if net > 0:
        total = min(candidates)
    elif net < 0:
        total = max(candidates)
    else:
        total = candidates[0]
    return total, candidates


def _compose_coc7_roll(tens: int, units: int) -> int:
    total = int(tens) * 10 + int(units)
    return 100 if total == 0 else total


def _coc7_success_level(total: int, target: int) -> str:
    if total == 1:
        return "critical"
    if total > target:
        return "failure"
    if total <= max(1, target // 5):
        return "extreme"
    if total <= max(1, target // 2):
        return "hard"
    return "regular"


def _roll_loss_expression(expression: str) -> int:
    expr = str(expression or "0").strip()
    if not expr:
        return 0
    if "d" in expr.lower():
        return dice.roll_dice(expr).total
    return _safe_int(expr, 0)


def _pc_from_target(session: GameSession, target: str) -> PlayerCharacter | None:
    if not target.startswith("pc:"):
        return None
    return session.player_by_character_name(target[3:])


def _skipped(ruleset_id: str, request: CheckRequest, reason: str) -> CheckResult:
    return CheckResult(
        applied=False,
        ruleset_id=ruleset_id,
        type=request.type,
        actor=request.actor,
        message=reason,
    )


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _safe_int(value, 0)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
