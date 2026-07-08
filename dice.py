from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

try:
    from .models import D20CheckResult, DiceResult
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import D20CheckResult, DiceResult


MAX_DICE_COUNT = 100
MAX_DICE_SIDES = 1000
_DICE_RE = re.compile(r"^\s*(?:(\d*)d(\d+))\s*([+-]\s*\d+)?\s*$", re.I)


@dataclass(frozen=True)
class DiceExpression:
    count: int
    sides: int
    modifier: int = 0

    def as_tuple(self) -> tuple[int, int, int]:
        return self.count, self.sides, self.modifier


def parse_dice_expression(expr: str) -> DiceExpression:
    match = _DICE_RE.match(expr or "")
    if not match:
        raise ValueError(f"invalid dice expression: {expr}")

    count_raw, sides_raw, modifier_raw = match.groups()
    count = int(count_raw) if count_raw else 1
    sides = int(sides_raw)
    modifier = int(modifier_raw.replace(" ", "")) if modifier_raw else 0

    if count < 1 or count > MAX_DICE_COUNT:
        raise ValueError(f"dice count must be between 1 and {MAX_DICE_COUNT}")
    if sides < 1 or sides > MAX_DICE_SIDES:
        raise ValueError(f"dice sides must be between 1 and {MAX_DICE_SIDES}")

    return DiceExpression(count=count, sides=sides, modifier=modifier)


def roll_dice(expr: str) -> DiceResult:
    parsed = parse_dice_expression(expr)
    rolls = [secrets.randbelow(parsed.sides) + 1 for _ in range(parsed.count)]
    return DiceResult(
        expression=expr.strip(),
        rolls=rolls,
        modifier=parsed.modifier,
        total=sum(rolls) + parsed.modifier,
    )


def roll_d20_check(attribute_value: int, dc: int) -> D20CheckResult:
    attr = int(attribute_value)
    target = int(dc)
    roll = secrets.randbelow(20) + 1
    modifier = (attr - 10) // 2
    total = roll + modifier
    natural = "nat20" if roll == 20 else "nat1" if roll == 1 else ""
    return D20CheckResult(
        attribute_value=attr,
        dc=target,
        roll=roll,
        attribute_modifier=modifier,
        total=total,
        success=total >= target,
        natural=natural,
    )
