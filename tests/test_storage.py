import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from models import CharacterPreset, GameSession, ScenarioScript
from storage import SessionStorage


class NoKVContext:
    pass


class KVContext:
    def __init__(self) -> None:
        self.data = {}

    async def get_kv_data(self, key):
        return self.data.get(key)

    async def put_kv_data(self, key, value):
        self.data[key] = value


def test_storage_saves_and_loads_presets_via_file_fallback():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        preset = CharacterPreset(
            name="艾莉丝",
            character_name="Alice",
            concept="敏捷的游侠",
            hp=12,
            san=48,
            inventory=["银钥匙"],
        )

        asyncio.run(storage.save_presets("u1", {"艾莉丝": preset}))
        loaded = asyncio.run(storage.load_presets("u1"))

        assert loaded == {"艾莉丝": preset}


def test_storage_keeps_presets_isolated_by_user_id():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        preset = CharacterPreset(
            name="艾莉丝",
            character_name="Alice",
            concept="敏捷的游侠",
        )

        asyncio.run(storage.save_presets("u1", {"艾莉丝": preset}))

        assert asyncio.run(storage.load_presets("u2")) == {}


def test_storage_saves_and_loads_global_scenario_scripts_via_file_fallback():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        script = ScenarioScript(
            script_id="fog-town",
            title="雾镇",
            summary="被浓雾封锁的小镇。",
        )

        asyncio.run(storage.save_scenario_scripts({"fog-town": script}))
        loaded = asyncio.run(storage.load_scenario_scripts())

        assert loaded == {"fog-town": script}
        assert (Path(tmp) / "scenario_scripts.json").exists()


def test_storage_saves_global_scenario_scripts_to_kv_and_file_cache():
    with TemporaryDirectory() as tmp:
        context = KVContext()
        storage = SessionStorage(context, Path(tmp))
        script = ScenarioScript(script_id="fog-town", title="雾镇")

        asyncio.run(storage.save_scenario_scripts({"fog-town": script}))

        assert "trpg_scenario_scripts" in context.data
        assert (Path(tmp) / "scenario_scripts.json").exists()


def test_storage_lists_saved_session_file_cache():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        session = GameSession.new(
            session_id="session-1",
            title="雾镇",
            theme="民俗恐怖",
            language="zh",
        )

        asyncio.run(storage.save_session(session))
        sessions = asyncio.run(storage.load_saved_sessions())

        assert [item.session_id for item in sessions] == ["session-1"]


def test_storage_finds_scenario_script_by_id_or_title():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        script = ScenarioScript(script_id="fog-town", title="雾镇")
        asyncio.run(storage.save_scenario_scripts({"fog-town": script}))

        assert asyncio.run(storage.find_scenario_script("fog-town")) == script
        assert asyncio.run(storage.find_scenario_script("雾镇")) == script
        assert asyncio.run(storage.find_scenario_script("不存在")) is None
