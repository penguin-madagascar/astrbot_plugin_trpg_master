import asyncio

from main import LLMTRPGPlugin, _apply_preset_update, _format_preset
from models import CharacterPreset, GameSession


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


def test_trpg_join_can_use_sender_owned_preset():
    session = GameSession.new(
        session_id="session-1",
        title="奇幻冒险",
        theme="奇幻冒险",
        language="zh",
    )
    storage = FakeStorage(
        session=session,
        presets={
            "u1": {
                "艾莉丝": CharacterPreset(
                    name="艾莉丝",
                    character_name="Alice",
                    concept="敏捷的游侠",
                    hp=12,
                    san=48,
                    inventory=["银钥匙"],
                )
            }
        },
    )
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = storage
    event = FakeEvent(user_id="u1", sender_name="Dana")

    outputs = asyncio.run(_collect(plugin.trpg_join(event, "preset:艾莉丝")))

    pc = session.players["u1"]
    assert outputs == ["角色已加入：Alice（HP 12 / SAN 48）"]
    assert pc.display_name == "Dana"
    assert pc.character_name == "Alice"
    assert pc.concept == "敏捷的游侠"
    assert pc.inventory == ["银钥匙"]


def test_trpg_join_keeps_existing_character_creation_syntax():
    session = GameSession.new(
        session_id="session-1",
        title="奇幻冒险",
        theme="奇幻冒险",
        language="zh",
    )
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = FakeStorage(session=session)
    event = FakeEvent(user_id="u1", sender_name="Dana")

    outputs = asyncio.run(_collect(plugin.trpg_join(event, "鲍勃 勇敢的战士")))

    pc = session.players["u1"]
    assert outputs == ["角色已加入：鲍勃（HP 10 / SAN 50）"]
    assert pc.character_name == "鲍勃"
    assert pc.concept == "勇敢的战士"


def test_trpg_preset_create_update_list_and_show():
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = FakeStorage()
    event = FakeEvent(user_id="u1", sender_name="Dana")

    created = asyncio.run(_collect(plugin.trpg_preset(event, "create 艾莉丝 敏捷的游侠")))
    updated = asyncio.run(_collect(plugin.trpg_preset(event, "update 艾莉丝 hp 12")))
    listed = asyncio.run(_collect(plugin.trpg_preset(event, "list")))
    shown = asyncio.run(_collect(plugin.trpg_preset(event, "show 艾莉丝")))

    assert created == ["角色预设已创建：艾莉丝"]
    assert updated == ["角色预设已更新：艾莉丝（hp=12）"]
    assert listed == ["你的角色预设：\n- 艾莉丝: 艾莉丝, HP 12, SAN 50, 敏捷的游侠"]
    assert "角色预设: 艾莉丝" in shown[0]
    assert "HP: 12 / SAN: 50" in shown[0]


class FakeEvent:
    unified_msg_origin = "session-1"

    def __init__(self, *, user_id: str, sender_name: str) -> None:
        self.user_id = user_id
        self.sender_name = sender_name

    def get_sender_id(self) -> str:
        return self.user_id

    def get_sender_name(self) -> str:
        return self.sender_name

    def plain_result(self, text: str) -> str:
        return text


class FakeStorage:
    def __init__(
        self,
        session: GameSession | None = None,
        presets: dict[str, dict[str, CharacterPreset]] | None = None,
    ) -> None:
        self.session = session
        self.presets = presets or {}

    async def load_session(self, session_id: str) -> GameSession | None:
        return self.session

    async def save_session(self, session: GameSession) -> None:
        self.session = session

    async def load_presets(self, owner_id: str) -> dict[str, CharacterPreset]:
        return dict(self.presets.get(owner_id, {}))

    async def save_presets(
        self,
        owner_id: str,
        presets: dict[str, CharacterPreset],
    ) -> None:
        self.presets[owner_id] = dict(presets)


async def _collect(generator):
    results = []
    async for item in generator:
        results.append(item)
    return results
