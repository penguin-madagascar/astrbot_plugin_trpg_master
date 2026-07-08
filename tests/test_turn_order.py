import asyncio

import main
from main import LLMTRPGPlugin
from models import GameSession, PlayerCharacter
from turn_order import (
    add_player_to_turn_order,
    advance_turn_order,
    current_turn_player,
    set_current_turn,
)


def test_old_session_deserialization_gets_default_turn_order():
    session = GameSession.from_dict(
        {
            "session_id": "session-1",
            "title": "奇幻冒险",
            "theme": "奇幻冒险",
            "language": "zh",
        }
    )

    assert session.turn_order.enabled is False
    assert session.turn_order.mode == "soft"
    assert session.turn_order.queue == []
    assert session.turn_order.current_index == 0
    assert session.turn_order.round_count == 1
    assert session.turn_order.paused is False


def test_turn_order_tracks_join_order_and_current_player():
    session = make_session()
    add_player_to_turn_order(session, "u1")
    add_player_to_turn_order(session, "u2")

    assert session.turn_order.queue == ["u1", "u2"]
    assert current_turn_player(session) == session.players["u1"]


def test_turn_order_advances_and_increments_round_on_wrap():
    session = make_session()
    add_player_to_turn_order(session, "u1")
    add_player_to_turn_order(session, "u2")

    assert advance_turn_order(session) == session.players["u2"]
    assert session.turn_order.current_index == 1
    assert session.turn_order.round_count == 1

    assert advance_turn_order(session) == session.players["u1"]
    assert session.turn_order.current_index == 0
    assert session.turn_order.round_count == 2


def test_turn_order_keeps_user_id_stable_for_rejoined_character():
    session = GameSession.new(
        session_id="session-1",
        title="奇幻冒险",
        theme="奇幻冒险",
        language="zh",
    )
    session.turn_order.enabled = True
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Dana",
        character_name="Alice",
        concept="游侠",
    )
    add_player_to_turn_order(session, "u1")
    session.players["u1"].character_name = "莉亚"
    add_player_to_turn_order(session, "u1")

    assert session.turn_order.queue == ["u1"]
    assert current_turn_player(session).character_name == "莉亚"


def test_set_current_turn_accepts_character_name_or_user_id():
    session = make_session()
    add_player_to_turn_order(session, "u1")
    add_player_to_turn_order(session, "u2")

    assert set_current_turn(session, "Bob") == session.players["u2"]
    assert session.turn_order.current_index == 1

    assert set_current_turn(session, "u1") == session.players["u1"]
    assert session.turn_order.current_index == 0


def test_trpg_start_sets_sender_as_default_gm(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return "开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    plugin = LLMTRPGPlugin(context=object(), config={"turn_order_enabled": True})
    plugin.storage = FakeStorage()
    event = FakeEvent(user_id="gm", sender_name="Keeper")

    outputs = asyncio.run(_collect(plugin.trpg_start(event, "雾镇")))

    assert outputs == ["开场。"]
    assert plugin.storage.session.turn_order.enabled is True
    assert plugin.storage.session.turn_order.gm_user_id == "gm"
    assert plugin.storage.session.turn_order.gm_display_name == "Keeper"


def test_trpg_join_adds_players_to_turn_queue():
    session = make_session()
    plugin = LLMTRPGPlugin(context=object(), config={"turn_order_enabled": True})
    plugin.storage = FakeStorage(session=session)

    output = asyncio.run(
        _collect(plugin.trpg_join(FakeEvent(user_id="u3", sender_name="Cara"), "Cara 学者"))
    )

    assert output == ["角色已加入：Cara（HP 10 / SAN 50）"]
    assert session.turn_order.queue == ["u1", "u2", "u3"]


def test_current_actor_action_advances_queue_and_uses_character_name(monkeypatch):
    captured = {}

    async def fake_call_gm(context, event, *, prompt, system_prompt):
        captured["prompt"] = prompt
        return "Alice 推开门。\n```json\n{}\n```"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "strict_json_patch": True},
    )
    plugin.storage = FakeStorage(session=session)

    outputs = asyncio.run(
        _collect(plugin.trpg_act(FakeEvent(user_id="u1", sender_name="Dana"), "推开门"))
    )

    assert outputs == ["Alice 推开门。"]
    assert "行动玩家：Alice" in captured["prompt"]
    assert session.turn_order.current_index == 1


def test_out_of_turn_action_warns_without_advancing(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return "Bob 观察走廊。\n```json\n{}\n```"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "strict_json_patch": True},
    )
    plugin.storage = FakeStorage(session=session)

    outputs = asyncio.run(
        _collect(plugin.trpg_act(FakeEvent(user_id="u2", sender_name="Morgan"), "观察"))
    )

    assert outputs[0].startswith("行动顺序提示：当前建议行动者是 Alice。")
    assert "Bob 观察走廊。" in outputs[0]
    assert session.turn_order.current_index == 0


def test_turn_control_requires_gm_for_management_commands():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "turn_control_requires_gm": True},
    )
    plugin.storage = FakeStorage(session=session)

    denied = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u2", sender_name="Morgan"), "next"))
    )
    allowed = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="gm", sender_name="Keeper"), "next"))
    )

    assert denied == ["只有 GM 可以管理行动顺序。"]
    assert allowed == ["行动顺序已推进。当前建议行动者：Bob"]
    assert session.turn_order.current_index == 1


def test_turn_control_can_be_opened_by_config():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "turn_control_requires_gm": False},
    )
    plugin.storage = FakeStorage(session=session)

    output = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u2", sender_name="Morgan"), "next"))
    )

    assert output == ["行动顺序已推进。当前建议行动者：Bob"]
    assert session.turn_order.current_index == 1


def test_turn_done_allows_current_player_or_gm_only():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True, "turn_control_requires_gm": True},
    )
    plugin.storage = FakeStorage(session=session)

    other = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u2", sender_name="Morgan"), "done"))
    )
    current = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u1", sender_name="Dana"), "done"))
    )
    gm = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="gm", sender_name="Keeper"), "done"))
    )

    assert other == ["只有当前行动者或 GM 可以结束当前行动。"]
    assert current == ["行动顺序已推进。当前建议行动者：Bob"]
    assert gm == ["行动顺序已推进。当前建议行动者：Alice"]
    assert session.turn_order.round_count == 2


def test_config_schema_contains_turn_order_settings():
    schema = main._load_config_schema()

    assert schema["turn_order_enabled"]["type"] == "bool"
    assert schema["turn_order_enabled"]["default"] is True
    assert schema["turn_control_requires_gm"]["type"] == "bool"
    assert schema["turn_control_requires_gm"]["default"] is True


def test_turn_order_config_values_are_exposed_and_coerced():
    schema = main._load_config_schema()
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = FakeStorage()

    dashboard = asyncio.run(plugin.web_dashboard())
    updates = main._coerce_config_updates(
        schema,
        {
            "turn_order_enabled": "false",
            "turn_control_requires_gm": "true",
        },
    )

    assert "turn_order_enabled" in dashboard["settings_schema"]
    assert "turn_control_requires_gm" in dashboard["settings_schema"]
    assert updates == {
        "turn_order_enabled": False,
        "turn_control_requires_gm": True,
    }


def make_session() -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="奇幻冒险",
        theme="奇幻冒险",
        language="zh",
    )
    session.turn_order.enabled = True
    session.turn_order.gm_user_id = "gm"
    session.turn_order.gm_display_name = "Keeper"
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Dana",
        character_name="Alice",
        concept="游侠",
    )
    session.players["u2"] = PlayerCharacter(
        user_id="u2",
        display_name="Morgan",
        character_name="Bob",
        concept="战士",
    )
    add_player_to_turn_order(session, "u1")
    add_player_to_turn_order(session, "u2")
    return session


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
    def __init__(self, session: GameSession | None = None) -> None:
        self.session = session

    async def find_scenario_script(self, query: str):
        return None

    async def load_session(self, session_id: str) -> GameSession | None:
        return self.session

    async def save_session(self, session: GameSession) -> None:
        self.session = session

    async def load_scenario_scripts(self):
        return {}


async def _collect(generator):
    results = []
    async for item in generator:
        results.append(item)
    return results
