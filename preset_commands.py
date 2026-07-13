from __future__ import annotations

try:
    from .models import DEFAULT_ATTRIBUTES, CharacterPreset
    from .rules import get_ruleset
except ImportError:  # pragma: no cover - direct module loading outside package.
    from models import DEFAULT_ATTRIBUTES, CharacterPreset
    from rules import get_ruleset


PRESET_TITLES = {
    "zh": "角色预设",
    "en": "Character Preset",
    "ja": "キャラクタープリセット",
    "ko": "캐릭터 프리셋",
}


def format_preset(language: str, preset: CharacterPreset) -> str:
    pc = preset.to_player_character(user_id="", display_name="")
    title = PRESET_TITLES.get(language, PRESET_TITLES["zh"])
    return f"{title}: {preset.name}\n" + get_ruleset(
        preset.ruleset_id
    ).format_character(pc)


def apply_preset_update(
    preset: CharacterPreset,
    field_name: str,
    raw_value: str,
) -> str:
    field = str(field_name or "").strip()
    value = str(raw_value or "").strip()
    field_lower = field.lower()
    field_upper = field.upper()
    if not field:
        raise ValueError("属性名称不能为空。")

    if field_lower in {"name", "character_name"}:
        if not value:
            raise ValueError("角色名不能为空。")
        preset.character_name = value
        return f"character_name={value}"
    if field_lower == "concept":
        if not value:
            raise ValueError("设定不能为空。")
        preset.concept = value
        return f"concept={value}"
    if field_lower == "hp":
        preset.hp = _parse_update_int(value, "hp")
        return f"hp={preset.hp}"
    if field_lower == "san":
        preset.san = _parse_update_int(value, "san")
        return f"san={preset.san}"
    if field_upper in DEFAULT_ATTRIBUTES:
        preset.attributes[field_upper] = _parse_update_int(value, field_upper)
        return f"{field_upper}={preset.attributes[field_upper]}"
    if field_lower.startswith("attr."):
        attr_name = field[5:].strip().upper()
        if not attr_name:
            raise ValueError("属性名称不能为空。")
        preset.attributes[attr_name] = _parse_update_int(value, attr_name)
        return f"{attr_name}={preset.attributes[attr_name]}"
    if field_lower.startswith("skill."):
        skill_name = field[6:].strip()
        if not skill_name:
            raise ValueError("技能名称不能为空。")
        preset.skills[skill_name] = _parse_update_int(value, skill_name)
        return f"{skill_name}={preset.skills[skill_name]}"
    if field_lower == "inventory":
        preset.inventory = split_list_value(value)
        return f"inventory={', '.join(preset.inventory) or '-'}"
    if field_lower in {"status", "status_effects"}:
        preset.status_effects = split_list_value(value)
        return f"status={', '.join(preset.status_effects) or '-'}"

    raise ValueError(f"不支持的属性名称：{field}")


def split_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if text == "-":
        return []
    for separator in ("，", "、"):
        text = text.replace(separator, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_update_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是整数。") from exc
