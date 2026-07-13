import asyncio
import json
from pathlib import Path

import main
from presentation import format_status
from main import LLMTRPGPlugin, PLUGIN_NAME
from models import GameSession, ScenarioScript
from scenario_io import coerce_config_updates, parse_scenario_import


def test_parse_scenario_json_import_accepts_single_script():
    payload = json.dumps(
        {
            "script_id": "fog-town",
            "title": "雾镇",
            "language": "zh",
            "theme": "民俗恐怖",
            "summary": "被浓雾封锁的小镇。",
            "background": "十年前的火灾仍无人提起。",
            "opening_scene": "玩家在祠堂醒来。",
            "hooks": ["钟楼停摆", "旧井低语"],
            "gm_notes": "慢节奏调查。",
            "tags": ["民俗", "调查"],
            "turn_order_mode": "soft",
        },
        ensure_ascii=False,
    )

    scripts = parse_scenario_import(payload, filename="scripts.json")

    assert scripts == [
        ScenarioScript(
            script_id="fog-town",
            title="雾镇",
            language="zh",
            theme="民俗恐怖",
            summary="被浓雾封锁的小镇。",
            background="十年前的火灾仍无人提起。",
            opening_scene="玩家在祠堂醒来。",
            hooks=["钟楼停摆", "旧井低语"],
            gm_notes="慢节奏调查。",
            tags=["民俗", "调查"],
            turn_order_mode="soft",
            created_at=scripts[0].created_at,
            updated_at=scripts[0].updated_at,
        )
    ]


def test_parse_scenario_json_import_accepts_play_mode_and_feature_flags():
    payload = json.dumps(
        {
            "script_id": "fog-town",
            "title": "雾镇",
            "play_mode": "custom",
            "feature_flags": {
                "command_agent_enabled": False,
                "turn_order_enabled": False,
                "structured_patch_enabled": False,
                "dice_requests_enabled": False,
                "state_patch_enabled": False,
                "knowledge_enabled": False,
                "second_pass_resolution_enabled": False,
            },
        },
        ensure_ascii=False,
    )

    script = parse_scenario_import(payload, filename="scripts.json")[0]

    assert script.play_mode == "custom"
    assert script.feature_flags == {
        "command_agent_enabled": False,
        "turn_order_enabled": False,
        "structured_patch_enabled": False,
        "dice_requests_enabled": False,
        "state_patch_enabled": False,
        "knowledge_enabled": False,
        "second_pass_resolution_enabled": False,
    }


def test_scenario_defaults_to_advanced_mode_for_existing_data():
    script = ScenarioScript.from_dict({"script_id": "fog-town", "title": "雾镇"})

    assert script.play_mode == "advanced"
    assert script.feature_flags["structured_patch_enabled"] is True


def test_parse_scenario_markdown_import_uses_expected_sections():
    markdown = """
# 雾镇

## 简介
被浓雾封锁的小镇。

## 背景
十年前的火灾仍无人提起。

## 开场场景
玩家在祠堂醒来。

## 线索
- 钟楼停摆
- 旧井低语

## GM 备注
慢节奏调查。

## 行动顺序
soft
""".strip()

    scripts = parse_scenario_import(markdown, filename="fog.md")
    script = scripts[0]

    assert script.title == "雾镇"
    assert script.theme == "雾镇"
    assert script.summary == "被浓雾封锁的小镇。"
    assert script.background == "十年前的火灾仍无人提起。"
    assert script.opening_scene == "玩家在祠堂醒来。"
    assert script.hooks == ["钟楼停摆", "旧井低语"]
    assert script.gm_notes == "慢节奏调查。"
    assert script.turn_order_mode == "soft"


def test_parse_scenario_markdown_import_supports_play_mode_and_flags():
    markdown = """
# 雾镇

## 模式
custom

## 机制开关
{
  "command_agent_enabled": false,
  "turn_order_enabled": false,
  "structured_patch_enabled": false,
  "dice_requests_enabled": false,
  "state_patch_enabled": false,
  "knowledge_enabled": false,
  "second_pass_resolution_enabled": false
}
""".strip()

    script = parse_scenario_import(markdown, filename="fog.md")[0]

    assert script.play_mode == "custom"
    assert all(value is False for value in script.feature_flags.values())


def test_parse_scenario_markdown_invalid_turn_order_mode_uses_default():
    markdown = """
# 雾镇

## turn_order_mode
invalid
""".strip()

    script = parse_scenario_import(markdown, filename="fog.md")[0]

    assert script.turn_order_mode == "llm_gm"


def test_parse_scenario_markdown_import_supports_ruleset_and_rule_nodes():
    markdown = """
# 雾镇

## 规则
coc7_lite

## 检定节点
[
  {
    "node_id": "library-spot",
    "title": "图书馆检定",
    "scene": "旧图书馆",
    "trigger": "调查书架",
    "check": {"type": "skill_check", "skill": "侦查"},
    "success": "发现账本。",
    "failure": "只发现灰尘。",
    "consequence": "失败会消耗时间。",
    "tags": ["调查"]
  }
]
""".strip()

    script = parse_scenario_import(markdown, filename="fog.md")[0]

    assert script.ruleset_id == "coc7_lite"
    assert script.rule_nodes[0].node_id == "library-spot"
    assert script.rule_nodes[0].check == {"type": "skill_check", "skill": "侦查"}


def testcoerce_config_updates_accepts_schema_keys_and_basic_types():
    schema = {
        "default_theme": {"type": "string"},
        "gm_system_prompt": {"type": "text"},
        "max_turns": {"type": "int"},
        "allow_state_patch": {"type": "bool"},
    }
    payload = {
        "default_theme": 123,
        "gm_system_prompt": "GM",
        "max_turns": "30",
        "allow_state_patch": "false",
        "ignored": "value",
    }

    updates = coerce_config_updates(schema, payload)

    assert updates == {
        "default_theme": "123",
        "gm_system_prompt": "GM",
        "max_turns": 30,
        "allow_state_patch": False,
    }


def test_web_save_settings_returns_400_for_invalid_integer(monkeypatch):
    class InvalidSettingsRequest:
        async def json(self, default=None):
            return {"max_turns": "many"}

    plugin = LLMTRPGPlugin(context=object(), config={"max_turns": 200})
    monkeypatch.setattr(main, "request", InvalidSettingsRequest())

    response = asyncio.run(plugin.web_save_settings())

    assert response == {
        "status": "error",
        "message": "max_turns must be an integer",
        "status_code": 400,
    }
    assert plugin.config["max_turns"] == 200


def test_plugin_registers_dashboard_web_api_routes():
    context = RegisteringContext()

    LLMTRPGPlugin(context=context)

    routes = {route for route, _handler, _methods, _desc in context.routes}
    assert f"/{PLUGIN_NAME}/dashboard" in routes
    assert f"/{PLUGIN_NAME}/settings/save" in routes
    assert f"/{PLUGIN_NAME}/scripts" in routes
    assert f"/{PLUGIN_NAME}/scripts/<script_id>" in routes
    assert f"/{PLUGIN_NAME}/scripts/save" in routes
    assert f"/{PLUGIN_NAME}/scripts/delete" in routes
    assert f"/{PLUGIN_NAME}/scripts/import" in routes
    assert f"/{PLUGIN_NAME}/scripts/export" in routes


def test_dashboard_exposes_script_turn_order_mode_field():
    html = Path("pages/dashboard/index.html").read_text(encoding="utf-8")
    js = Path("pages/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="script-turn-order-mode"' in html
    assert 'value="llm_gm"' in html
    assert 'value="soft"' in html
    assert "turn_order_mode: document.getElementById(\"script-turn-order-mode\")" in js
    assert "turn_order_mode: scriptFields.turn_order_mode.value" in js
    assert "turnOrderModeLabel(script.turn_order_mode)" in js


def test_dashboard_exposes_script_ruleset_and_rule_nodes_fields():
    html = Path("pages/dashboard/index.html").read_text(encoding="utf-8")
    js = Path("pages/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="script-ruleset-id"' in html
    assert 'value="d20_lite"' in html
    assert 'value="coc7_lite"' in html
    assert 'id="script-rule-nodes"' in html
    assert "ruleset_id: document.getElementById(\"script-ruleset-id\")" in js
    assert "rule_nodes: parseRuleNodes(scriptFields.rule_nodes.value)" in js
    assert "formatRuleNodes(script.rule_nodes || [])" in js


def test_dashboard_exposes_script_play_mode_and_feature_flags_fields():
    html = Path("pages/dashboard/index.html").read_text(encoding="utf-8")
    js = Path("pages/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="script-play-mode"' in html
    assert 'value="simple"' in html
    assert 'value="advanced"' in html
    assert 'value="custom"' in html
    assert 'id="script-feature-flags"' in html
    assert "play_mode: document.getElementById(\"script-play-mode\")" in js
    assert "feature_flags: collectFeatureFlags()" in js
    assert "playModeLabel(script.play_mode)" in js


def test_trpg_start_uses_matching_scenario_script(monkeypatch):
    captured = {}

    async def fake_call_gm(context, event, *, prompt, system_prompt):
        captured["prompt"] = prompt
        return "祠堂木门自行合上。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    script = ScenarioScript(
        script_id="fog-town",
        title="雾镇",
        language="zh",
        theme="民俗恐怖",
        summary="被浓雾封锁的小镇。",
        background="十年前的火灾仍无人提起。",
        opening_scene="玩家在祠堂醒来。",
        hooks=["钟楼停摆", "旧井低语"],
        gm_notes="慢节奏调查。",
        turn_order_mode="soft",
        ruleset_id="coc7_lite",
        rule_nodes=[
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
    )
    storage = FakeStorage({"fog-town": script})
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": False, "turn_order_mode": "llm_gm"},
    )
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "雾镇")))

    assert outputs == ["祠堂木门自行合上。"]
    assert storage.session.title == "雾镇"
    assert storage.session.theme == "民俗恐怖"
    assert storage.session.language == "zh"
    assert storage.session.ruleset_id == "coc7_lite"
    assert storage.session.turn_order.enabled is True
    assert storage.session.turn_order.mode == "soft"
    assert storage.session.scenario_script["script_id"] == "fog-town"
    assert storage.session.scenario_script["turn_order_mode"] == "soft"
    assert storage.session.scenario_script["ruleset_id"] == "coc7_lite"
    assert storage.session.scenario_script["rule_nodes"][0]["title"] == "图书馆检定"
    assert "被浓雾封锁的小镇。" in captured["prompt"]
    assert "十年前的火灾仍无人提起。" in captured["prompt"]
    assert "玩家在祠堂醒来。" in captured["prompt"]
    assert "钟楼停摆" in captured["prompt"]
    assert "慢节奏调查。" in captured["prompt"]
    assert "CoC 7e Lite" in captured["prompt"]
    assert "图书馆检定" in captured["prompt"]


def test_trpg_start_free_theme_defaults_to_simple_mode(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        assert "简易模式" in prompt
        return "自由开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    storage = FakeStorage({})
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "turn_order_mode": "llm_gm"},
    )
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "海上奇遇")))

    assert outputs == ["自由开场。"]
    assert storage.session.title == "海上奇遇"
    assert storage.session.play_mode == "simple"
    assert storage.session.feature_flags["structured_patch_enabled"] is False
    assert storage.session.turn_order.enabled is False


def test_trpg_start_free_theme_can_request_advanced_mode(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        assert "JSON" in prompt
        return "进阶开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    storage = FakeStorage({})
    plugin = LLMTRPGPlugin(context=object(), config={"turn_order_mode": "soft"})
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "进阶 海上奇遇")))

    assert outputs == ["进阶开场。"]
    assert storage.session.title == "海上奇遇"
    assert storage.session.play_mode == "advanced"
    assert storage.session.feature_flags["structured_patch_enabled"] is True
    assert storage.session.turn_order.enabled is True


def test_trpg_start_keeps_free_theme_when_no_scenario_matches(monkeypatch):
    captured = {}

    async def fake_call_gm(context, event, *, prompt, system_prompt):
        captured["prompt"] = prompt
        return "自由开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    script = ScenarioScript(script_id="fog-town", title="雾镇")
    storage = FakeStorage({"fog-town": script})
    plugin = LLMTRPGPlugin(
        context=object(),
        config={
            "turn_order_enabled": True,
            "turn_order_mode": "soft",
            "default_ruleset_id": "coc7_lite",
        },
    )
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "进阶 海上奇遇")))

    assert outputs == ["自由开场。"]
    assert storage.session.title == "海上奇遇"
    assert storage.session.theme == "海上奇遇"
    assert storage.session.ruleset_id == "coc7_lite"
    assert storage.session.turn_order.enabled is True
    assert storage.session.turn_order.mode == "soft"
    assert storage.session.scenario_script is None
    assert "主题：海上奇遇" in captured["prompt"]
    assert "被浓雾封锁的小镇" not in captured["prompt"]


def test_trpg_status_includes_ruleset_and_script_rule_nodes():
    session = GameSession.new(
        session_id="session-1",
        title="雾镇",
        theme="民俗恐怖",
        language="zh",
        ruleset_id="coc7_lite",
    )
    script = ScenarioScript(
        script_id="fog-town",
        title="雾镇",
        ruleset_id="coc7_lite",
        rule_nodes=[
            {
                "node_id": "library-spot",
                "title": "图书馆检定",
                "check": {"type": "skill_check", "skill": "侦查"},
            }
        ],
    )
    session.scenario_script = script.to_session_context()
    text = format_status(session)

    assert "Ruleset: coc7_lite" in text
    assert "Rule Nodes:\n- 图书馆检定" in text


class RegisteringContext:
    def __init__(self) -> None:
        self.routes = []

    def register_web_api(self, route, handler, methods, desc):
        self.routes.append((route, handler, methods, desc))


class FakeEvent:
    unified_msg_origin = "session-1"

    def get_sender_id(self) -> str:
        return "u1"

    def get_sender_name(self) -> str:
        return "Dana"

    def plain_result(self, text: str) -> str:
        return text


class FakeStorage:
    def __init__(self, scripts: dict[str, ScenarioScript]) -> None:
        self.scripts = scripts
        self.session = None

    async def find_scenario_script(self, query: str) -> ScenarioScript | None:
        normalized = str(query or "").strip()
        for script in self.scripts.values():
            if script.script_id == normalized or script.title == normalized:
                return script
        return None

    async def load_session(self, session_id: str):
        return self.session

    async def save_session(self, session):
        self.session = session


async def _collect(generator):
    results = []
    async for item in generator:
        results.append(item)
    return results
