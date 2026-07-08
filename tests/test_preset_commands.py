from main import _apply_preset_update, _format_preset
from models import CharacterPreset


def test_apply_preset_update_changes_scalar_fields_and_attributes():
    preset = CharacterPreset(
        name="艾莉丝",
        character_name="Alice",
        concept="敏捷的游侠",
    )

    _apply_preset_update(preset, "name", "莉亚")
    _apply_preset_update(preset, "concept", "古城来的 探索者")
    _apply_preset_update(preset, "hp", "12")
    _apply_preset_update(preset, "san", "48")
    _apply_preset_update(preset, "STR", "14")
    _apply_preset_update(preset, "attr.dex", "13")

    assert preset.name == "艾莉丝"
    assert preset.character_name == "莉亚"
    assert preset.concept == "古城来的 探索者"
    assert preset.hp == 12
    assert preset.san == 48
    assert preset.attributes["STR"] == 14
    assert preset.attributes["DEX"] == 13


def test_apply_preset_update_changes_skills_inventory_and_status():
    preset = CharacterPreset(
        name="艾莉丝",
        character_name="Alice",
        concept="敏捷的游侠",
    )

    _apply_preset_update(preset, "skill.潜行", "60")
    _apply_preset_update(preset, "inventory", "银钥匙，火把、绳索")
    _apply_preset_update(preset, "status", "警觉,轻伤")

    assert preset.skills == {"潜行": 60}
    assert preset.inventory == ["银钥匙", "火把", "绳索"]
    assert preset.status_effects == ["警觉", "轻伤"]

    _apply_preset_update(preset, "inventory", "-")
    _apply_preset_update(preset, "status", "-")

    assert preset.inventory == []
    assert preset.status_effects == []


def test_apply_preset_update_rejects_unknown_fields_and_bad_integers():
    preset = CharacterPreset(
        name="艾莉丝",
        character_name="Alice",
        concept="敏捷的游侠",
    )

    _assert_value_error(lambda: _apply_preset_update(preset, "unknown", "1"))
    _assert_value_error(lambda: _apply_preset_update(preset, "hp", "bad"))
    _assert_value_error(lambda: _apply_preset_update(preset, "skill.", "60"))


def test_format_preset_includes_complete_character_card():
    preset = CharacterPreset(
        name="艾莉丝",
        character_name="Alice",
        concept="敏捷的游侠",
        hp=12,
        san=48,
        attributes={"STR": 14},
        skills={"潜行": 60},
        inventory=["银钥匙"],
        status_effects=["警觉"],
    )

    text = _format_preset("zh", preset)

    assert "角色预设: 艾莉丝" in text
    assert "Character: Alice" in text
    assert "Concept: 敏捷的游侠" in text
    assert "HP: 12 / SAN: 48" in text
    assert "STR 14" in text
    assert "潜行 60" in text
    assert "Inventory: 银钥匙" in text
    assert "Status: 警觉" in text


def _assert_value_error(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("expected ValueError")
