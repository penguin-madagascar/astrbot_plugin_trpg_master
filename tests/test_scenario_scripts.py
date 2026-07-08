import asyncio
import json
from pathlib import Path

import main
from main import (
    LLMTRPGPlugin,
    PLUGIN_NAME,
    _coerce_config_updates,
    _parse_scenario_import,
)
from models import ScenarioScript


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
        },
        ensure_ascii=False,
    )

    scripts = _parse_scenario_import(payload, filename="scripts.json")

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
            created_at=scripts[0].created_at,
            updated_at=scripts[0].updated_at,
        )
    ]


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
""".strip()

    scripts = _parse_scenario_import(markdown, filename="fog.md")
    script = scripts[0]

    assert script.title == "雾镇"
    assert script.theme == "雾镇"
    assert script.summary == "被浓雾封锁的小镇。"
    assert script.background == "十年前的火灾仍无人提起。"
    assert script.opening_scene == "玩家在祠堂醒来。"
    assert script.hooks == ["钟楼停摆", "旧井低语"]
    assert script.gm_notes == "慢节奏调查。"


def test_coerce_config_updates_accepts_schema_keys_and_basic_types():
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

    updates = _coerce_config_updates(schema, payload)

    assert updates == {
        "default_theme": "123",
        "gm_system_prompt": "GM",
        "max_turns": 30,
        "allow_state_patch": False,
    }


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
    )
    storage = FakeStorage({"fog-town": script})
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "雾镇")))

    assert outputs == ["祠堂木门自行合上。"]
    assert storage.session.title == "雾镇"
    assert storage.session.theme == "民俗恐怖"
    assert storage.session.language == "zh"
    assert storage.session.scenario_script["script_id"] == "fog-town"
    assert "被浓雾封锁的小镇。" in captured["prompt"]
    assert "十年前的火灾仍无人提起。" in captured["prompt"]
    assert "玩家在祠堂醒来。" in captured["prompt"]
    assert "钟楼停摆" in captured["prompt"]
    assert "慢节奏调查。" in captured["prompt"]


def test_trpg_start_keeps_free_theme_when_no_scenario_matches(monkeypatch):
    captured = {}

    async def fake_call_gm(context, event, *, prompt, system_prompt):
        captured["prompt"] = prompt
        return "自由开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    script = ScenarioScript(script_id="fog-town", title="雾镇")
    storage = FakeStorage({"fog-town": script})
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = storage

    outputs = asyncio.run(_collect(plugin.trpg_start(FakeEvent(), "海上奇遇")))

    assert outputs == ["自由开场。"]
    assert storage.session.title == "海上奇遇"
    assert storage.session.theme == "海上奇遇"
    assert storage.session.scenario_script is None
    assert "主题：海上奇遇" in captured["prompt"]
    assert "被浓雾封锁的小镇" not in captured["prompt"]


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
