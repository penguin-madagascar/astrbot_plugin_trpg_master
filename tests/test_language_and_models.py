from language import detect_language_from_theme
from models import CharacterPreset, GameSession, PlayerCharacter, ScenarioScript


def test_detect_language_from_theme_uses_chinese_for_empty_or_uncertain_text():
    assert detect_language_from_theme("") == "zh"
    assert detect_language_from_theme("??? 123") == "zh"


def test_detect_language_from_theme_identifies_common_scripts():
    assert detect_language_from_theme("被雾吞没的古镇") == "zh"
    assert detect_language_from_theme("A haunted lighthouse on the winter coast") == "en"
    assert detect_language_from_theme("霧の古い神社で始まる怪談") == "ja"
    assert detect_language_from_theme("안개 속의 오래된 저택") == "ko"


def test_game_session_serialization_preserves_language_and_players():
    session = GameSession.new(
        session_id="umo-1",
        title="Haunted Lighthouse",
        theme="Haunted Lighthouse",
        language="en",
    )
    session.players["42"] = PlayerCharacter(
        user_id="42",
        display_name="Dana",
        character_name="Mara",
        concept="Former sailor",
    )
    session.turn_count = 3

    restored = GameSession.from_dict(session.to_dict())

    assert restored.language == "en"
    assert restored.turn_count == 3
    assert restored.players["42"].character_name == "Mara"


def test_character_preset_serialization_restores_defaults_and_full_card():
    preset = CharacterPreset.from_dict(
        {
            "name": "艾莉丝",
            "character_name": "Alice",
            "concept": "敏捷的游侠",
            "hp": "12",
            "san": 48,
            "attributes": {"str": 14},
            "skills": {"潜行": "60"},
            "inventory": ["银钥匙"],
            "status_effects": ["警觉"],
        }
    )

    assert preset.name == "艾莉丝"
    assert preset.character_name == "Alice"
    assert preset.hp == 12
    assert preset.san == 48
    assert preset.attributes["STR"] == 14
    assert preset.attributes["DEX"] == 10
    assert preset.skills == {"潜行": 60}
    assert preset.inventory == ["银钥匙"]
    assert preset.status_effects == ["警觉"]

    restored = CharacterPreset.from_dict(preset.to_dict())

    assert restored == preset


def test_character_preset_to_player_character_clones_mutable_fields():
    preset = CharacterPreset(
        name="艾莉丝",
        character_name="Alice",
        concept="敏捷的游侠",
        attributes={"STR": 14, "DEX": 12},
        skills={"潜行": 60},
        inventory=["银钥匙"],
        status_effects=["警觉"],
    )

    pc = preset.to_player_character(user_id="u1", display_name="Dana")
    pc.attributes["STR"] = 8
    pc.skills["潜行"] = 10
    pc.inventory.append("火把")
    pc.status_effects.clear()

    assert pc.user_id == "u1"
    assert pc.display_name == "Dana"
    assert pc.character_name == "Alice"
    assert preset.attributes["STR"] == 14
    assert preset.skills["潜行"] == 60
    assert preset.inventory == ["银钥匙"]
    assert preset.status_effects == ["警觉"]


def test_scenario_script_serialization_restores_defaults_and_context():
    script = ScenarioScript.from_dict(
        {
            "script_id": "fog-town",
            "title": "雾镇",
            "language": "zh",
            "summary": "被浓雾封锁的小镇。",
            "hooks": ["钟楼停摆", "旧井低语"],
            "tags": ["民俗", "调查"],
        }
    )

    assert script.script_id == "fog-town"
    assert script.title == "雾镇"
    assert script.theme == "雾镇"
    assert script.background == ""
    assert script.opening_scene == ""
    assert script.hooks == ["钟楼停摆", "旧井低语"]
    assert script.gm_notes == ""
    assert script.tags == ["民俗", "调查"]
    assert script.created_at
    assert script.updated_at

    restored = ScenarioScript.from_dict(script.to_dict())

    assert restored == script
    assert restored.to_session_context() == {
        "script_id": "fog-town",
        "title": "雾镇",
        "summary": "被浓雾封锁的小镇。",
        "background": "",
        "opening_scene": "",
        "hooks": ["钟楼停摆", "旧井低语"],
        "gm_notes": "",
        "tags": ["民俗", "调查"],
    }


def test_game_session_serialization_preserves_scenario_script_context():
    script = ScenarioScript(
        script_id="fog-town",
        title="雾镇",
        summary="被浓雾封锁的小镇。",
    )
    session = GameSession.new(
        session_id="umo-1",
        title=script.title,
        theme=script.theme,
        language=script.language,
    )
    session.scenario_script = script.to_session_context()

    restored = GameSession.from_dict(session.to_dict())

    assert restored.scenario_script == script.to_session_context()
