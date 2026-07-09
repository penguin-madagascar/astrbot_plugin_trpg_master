from models import GameSession, PlayerCharacter
from state import apply_state_patches


def make_session() -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="奇幻冒险",
        theme="奇幻冒险",
        language="zh",
    )
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Alice",
        character_name="艾莉丝",
        concept="敏捷的游侠",
    )
    return session


def test_apply_state_patches_allows_hp_and_san_delta_with_floor():
    session = make_session()

    results = apply_state_patches(
        session,
        [
            {"target": "pc:艾莉丝", "op": "hp_delta", "value": -99, "reason": "重伤"},
            {"target": "pc:艾莉丝", "op": "san_delta", "value": "-60", "reason": "恐惧"},
        ],
    )

    pc = session.players["u1"]
    assert pc.hp == 0
    assert pc.san == 0
    assert [result.applied for result in results] == [True, True]
    assert "HP" in results[0].message
    assert "SAN" in results[1].message


def test_apply_state_patches_allows_inventory_and_status_changes():
    session = make_session()

    results = apply_state_patches(
        session,
        [
            {"target": "pc:艾莉丝", "op": "add_item", "value": "银钥匙"},
            {"target": "pc:艾莉丝", "op": "add_status", "value": "流血"},
            {"target": "pc:艾莉丝", "op": "remove_item", "value": "银钥匙"},
            {"target": "pc:艾莉丝", "op": "remove_status", "value": "流血"},
        ],
    )

    pc = session.players["u1"]
    assert pc.inventory == []
    assert pc.status_effects == []
    assert all(result.applied for result in results)


def test_apply_state_patches_skips_unknown_or_unsafe_operations():
    session = make_session()

    results = apply_state_patches(
        session,
        [
            {"target": "npc:守卫", "op": "hp_delta", "value": -1},
            {"target": "pc:不存在", "op": "hp_delta", "value": -1},
            {"target": "pc:艾莉丝", "op": "set_hp", "value": 999},
            {"target": "pc:艾莉丝", "op": "hp_delta", "value": "bad"},
        ],
    )

    assert session.players["u1"].hp == 10
    assert [result.applied for result in results] == [False, False, False, False]
    assert "unsupported target" in results[0].message
    assert "not found" in results[1].message
    assert "unsupported op" in results[2].message
    assert "invalid integer" in results[3].message


def test_apply_state_patches_delegates_semistrict_ruleset_ops():
    session = make_session()

    results = apply_state_patches(
        session,
        [
            {"target": "pc:艾莉丝", "op": "damage", "value": 3},
            {"target": "pc:艾莉丝", "op": "resource_delta", "field": "mp", "value": 2},
            {"target": "pc:艾莉丝", "op": "skill_delta", "field": "潜行", "value": 5},
        ],
    )

    pc = session.players["u1"]
    assert pc.hp == 7
    assert pc.ruleset_data["mp"] == 2
    assert pc.skills["潜行"] == 5
    assert [result.applied for result in results] == [True, True, True]
