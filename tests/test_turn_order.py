import asyncio

import main
from main import LLMTRPGPlugin
from models import GameSession, PlayerCharacter
from prompts import build_action_prompt
from turn_order import (
    add_player_to_turn_order,
    advance_turn_order,
    current_turn_player,
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


def test_turn_order_state_dict_does_not_include_player_gm_fields():
    session = make_session()
    payload = session.turn_order.to_dict()

    assert "gm_user_id" not in payload
    assert "gm_display_name" not in payload


def test_status_and_action_prompt_do_not_include_player_gm_fields():
    session = make_session()
    plugin = LLMTRPGPlugin(context=object())
    status = plugin._format_turn_order(session)
    prompt = build_action_prompt(session, "Alice", "观察门口")

    assert "GM:" not in status
    assert "gm_user_id" not in prompt
    assert "gm_display_name" not in prompt


def test_trpg_start_initializes_turn_order_without_player_gm(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return "开场。"

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    plugin = LLMTRPGPlugin(context=object(), config={"turn_order_enabled": True})
    plugin.storage = FakeStorage()
    event = FakeEvent(user_id="gm", sender_name="Keeper")

    outputs = asyncio.run(_collect(plugin.trpg_start(event, "雾镇")))

    assert outputs == ["开场。"]
    assert plugin.storage.session.turn_order.enabled is True
    assert "gm_user_id" not in plugin.storage.session.turn_order.to_dict()
    assert "gm_display_name" not in plugin.storage.session.turn_order.to_dict()


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


def test_current_actor_can_advance_turn_order_with_next():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True},
    )
    plugin.storage = FakeStorage(session=session)

    output = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u1", sender_name="Dana"), "next"))
    )

    assert output == ["行动顺序已推进。当前建议行动者：Bob"]
    assert session.turn_order.current_index == 1


def test_turn_next_and_done_reject_non_current_player():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True},
    )
    plugin.storage = FakeStorage(session=session)

    next_output = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u2", sender_name="Morgan"), "next"))
    )
    done_output = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u2", sender_name="Morgan"), "done"))
    )

    assert next_output == ["只有当前行动者可以推进行动顺序。"]
    assert done_output == ["只有当前行动者可以推进行动顺序。"]
    assert session.turn_order.current_index == 0


def test_turn_done_allows_current_player_only():
    session = make_session()
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"turn_order_enabled": True},
    )
    plugin.storage = FakeStorage(session=session)

    current = asyncio.run(
        _collect(plugin.trpg_turn(FakeEvent(user_id="u1", sender_name="Dana"), "done"))
    )

    assert current == ["行动顺序已推进。当前建议行动者：Bob"]
    assert session.turn_order.current_index == 1


def test_removed_turn_management_actions_show_usage():
    session = make_session()
    plugin = LLMTRPGPlugin(context=object(), config={"turn_order_enabled": True})
    plugin.storage = FakeStorage(session=session)

    for action in ("gm Bob", "set Bob", "skip", "pause", "resume"):
        output = asyncio.run(
            _collect(plugin.trpg_turn(FakeEvent(user_id="u1", sender_name="Dana"), action))
        )

        assert output == ["用法：/trpg_turn [done|next]"]
        assert session.turn_order.current_index == 0


def test_config_schema_contains_turn_order_settings():
    schema = main._load_config_schema()

    assert schema["turn_order_enabled"]["type"] == "bool"
    assert schema["turn_order_enabled"]["default"] is True
    assert "turn_control_requires_gm" not in schema


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
    assert "turn_control_requires_gm" not in dashboard["settings_schema"]
    assert updates == {"turn_order_enabled": False}


def make_session() -> GameSession:
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
