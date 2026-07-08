import pathlib
import random

import pytest

import dice


def test_parse_dice_expression_accepts_supported_forms():
    assert dice.parse_dice_expression("d20").as_tuple() == (1, 20, 0)
    assert dice.parse_dice_expression("1d20+3").as_tuple() == (1, 20, 3)
    assert dice.parse_dice_expression("2d6").as_tuple() == (2, 6, 0)
    assert dice.parse_dice_expression("1d100").as_tuple() == (1, 100, 0)
    assert dice.parse_dice_expression("4d8-2").as_tuple() == (4, 8, -2)


def test_roll_dice_uses_secure_random_and_returns_each_die(monkeypatch):
    values = iter([0, 5])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(values))

    result = dice.roll_dice("2d6+3")

    assert result.expression == "2d6+3"
    assert result.rolls == [1, 6]
    assert result.modifier == 3
    assert result.total == 10


@pytest.mark.parametrize(
    "expression",
    ["", "abc", "0d6", "101d6", "1d0", "1d1001", "1d6+bad", "1d6+2d4"],
)
def test_parse_dice_expression_rejects_invalid_or_unsafe_forms(expression):
    with pytest.raises(ValueError):
        dice.parse_dice_expression(expression)


def test_roll_d20_check_calculates_attribute_modifier(monkeypatch):
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: 9)

    result = dice.roll_d20_check(attribute_value=14, dc=12)

    assert result.roll == 10
    assert result.attribute_modifier == 2
    assert result.total == 12
    assert result.success is True
    assert result.natural == ""


def test_roll_d20_check_marks_natural_20(monkeypatch):
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: 19)

    result = dice.roll_d20_check(attribute_value=8, dc=99)

    assert result.roll == 20
    assert result.attribute_modifier == -1
    assert result.total == 19
    assert result.success is False
    assert result.natural == "nat20"


def test_dice_module_does_not_import_random():
    source = pathlib.Path(dice.__file__).read_text(encoding="utf-8")

    assert "import random" not in source
    assert random.__name__ == "random"
