from language import detect_language_from_theme
from models import CharacterPreset, GameSession, PlayerCharacter, ScenarioScript
from presentation import message


def test_presentation_uses_requested_language_and_chinese_fallback():
    assert message("en", "member_required").startswith("Only players")
    assert message("missing", "member_required") == "只有已加入当前跑团的玩家可以执行此操作。"


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
    assert preset.ruleset_id == "d20_lite"
    assert preset.ruleset_data == {}

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
    assert pc.ruleset_id == "d20_lite"
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
    assert script.turn_order_mode == "llm_gm"
    assert script.ruleset_id == "d20_lite"
    assert script.rule_nodes == []
    assert script.created_at
    assert script.updated_at

    restored = ScenarioScript.from_dict(script.to_dict())

    assert restored == script
    assert restored.to_session_context() == {
        "script_id": "fog-town",
        "title": "雾镇",
        "play_mode": "advanced",
        "summary": "被浓雾封锁的小镇。",
        "background": "",
        "opening_scene": "",
        "hooks": ["钟楼停摆", "旧井低语"],
        "gm_notes": "",
        "tags": ["民俗", "调查"],
        "turn_order_mode": "llm_gm",
        "ruleset_id": "d20_lite",
        "rule_nodes": [],
        "feature_flags": {
            "command_agent_enabled": True,
            "turn_order_enabled": True,
            "structured_patch_enabled": True,
            "dice_requests_enabled": True,
            "state_patch_enabled": True,
            "knowledge_enabled": True,
            "second_pass_resolution_enabled": True,
        },
    }


def test_scenario_script_preserves_valid_turn_order_mode_and_normalizes_invalid():
    soft_script = ScenarioScript.from_dict(
        {
            "script_id": "fog-town",
            "title": "雾镇",
            "turn_order_mode": "soft",
        }
    )
    invalid_script = ScenarioScript.from_dict(
        {
            "script_id": "bad-town",
            "title": "坏镇",
            "turn_order_mode": "unknown",
        }
    )

    assert soft_script.turn_order_mode == "soft"
    assert soft_script.to_dict()["turn_order_mode"] == "soft"
    assert soft_script.to_session_context()["turn_order_mode"] == "soft"
    assert invalid_script.turn_order_mode == "llm_gm"


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
    assert restored.ruleset_id == "d20_lite"


def test_models_preserve_ruleset_specific_fields():
    preset = CharacterPreset.from_dict(
        {
            "name": "艾莉丝",
            "character_name": "Alice",
            "concept": "调查员",
            "ruleset_id": "coc7_lite",
            "ruleset_data": {"luck": "45", "mp": 10},
        }
    )
    script = ScenarioScript.from_dict(
        {
            "script_id": "fog-town",
            "title": "雾镇",
            "ruleset_id": "coc7_lite",
            "rule_nodes": [
                {
                    "node_id": "library-spot",
                    "title": "图书馆检定",
                    "scene": "旧图书馆",
                    "trigger": "调查书架",
                    "check": {"type": "skill_check", "skill": "侦查"},
                    "success": "发现账本。",
                    "failure": "只发现灰尘。",
                    "consequence": "失败会消耗时间。",
                    "tags": ["调查"],
                }
            ],
        }
    )

    pc = preset.to_player_character(user_id="u1", display_name="Dana")

    assert preset.ruleset_id == "coc7_lite"
    assert preset.ruleset_data == {"luck": "45", "mp": 10}
    assert pc.ruleset_id == "coc7_lite"
    assert pc.ruleset_data == {"luck": "45", "mp": 10}
    assert script.ruleset_id == "coc7_lite"
    assert script.rule_nodes[0].node_id == "library-spot"
    assert script.to_session_context()["rule_nodes"][0]["check"]["skill"] == "侦查"
