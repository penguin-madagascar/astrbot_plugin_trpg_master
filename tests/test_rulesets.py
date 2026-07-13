import dice

from models import GameSession, PlayerCharacter
from rules import (
    CheckRequest,
    apply_ruleset_state_patch,
    get_ruleset,
    list_rulesets,
    resolve_check_request,
)


def make_session(*, ruleset_id: str = "d20_lite") -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="规则测试",
        theme="规则测试",
        language="zh",
        ruleset_id=ruleset_id,
    )
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Dana",
        character_name="艾莉丝",
        concept="调查员",
        ruleset_id=ruleset_id,
        hp=10,
        san=50,
        attributes={"STR": 14, "DEX": 12, "INT": 15},
        skills={"潜行": 60, "侦查": 55},
        ruleset_data={"luck": 45, "mp": 10},
    )
    session.players["u2"] = PlayerCharacter(
        user_id="u2",
        display_name="Rin",
        character_name="鲍勃",
        concept="守卫",
        ruleset_id=ruleset_id,
        hp=12,
        san=40,
        attributes={"STR": 10, "DEX": 10, "INT": 10},
        skills={"潜行": 30, "侦查": 35},
    )
    return session


def test_ruleset_registry_exposes_initial_rulesets():
    assert {ruleset.ruleset_id for ruleset in list_rulesets()} >= {
        "d20_lite",
        "coc7_lite",
    }
    assert get_ruleset("missing").ruleset_id == "d20_lite"


def test_d20_lite_resolves_legacy_skill_check(monkeypatch):
    session = make_session()
    rolls = iter([9])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))

    result = resolve_check_request(
        session,
        {
            "type": "skill_check",
            "actor": "艾莉丝",
            "skill": "DEX",
            "dc": 11,
            "reason": "躲避落石",
        },
    )

    assert result.applied is True
    assert result.success is True
    assert result.ruleset_id == "d20_lite"
    assert result.rolls == [10]
    assert result.total == 11
    assert "艾莉丝 DEX vs DC 11" in result.message


def test_d20_lite_supports_advantage_and_opposed_checks(monkeypatch):
    session = make_session()
    rolls = iter([3, 17, 10])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))

    advantage = resolve_check_request(
        session,
        CheckRequest(
            type="skill_check",
            actor="艾莉丝",
            skill="STR",
            dc=15,
            advantage="advantage",
        ),
    )
    opposed = resolve_check_request(
        session,
        {
            "type": "opposed_check",
            "actor": "艾莉丝",
            "opponent": "鲍勃",
            "skill": "STR",
        },
    )

    assert advantage.rolls == [4, 18]
    assert advantage.total == 20
    assert advantage.success is True
    assert opposed.total == 13
    assert opposed.opponent_total == 10
    assert opposed.success is True


def test_coc7_lite_resolves_success_levels_and_bonus_die(monkeypatch):
    session = make_session(ruleset_id="coc7_lite")
    rolls = iter([2, 4, 3])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))

    result = resolve_check_request(
        session,
        {
            "type": "skill_check",
            "actor": "艾莉丝",
            "skill": "侦查",
            "bonus_dice": 1,
            "reason": "查看壁画",
        },
    )

    assert result.ruleset_id == "coc7_lite"
    assert result.rolls == [42, 32]
    assert result.total == 32
    assert result.target == 55
    assert result.success is True
    assert result.success_level == "regular"
    assert "regular success" in result.message


def test_coc7_lite_san_check_can_apply_san_loss(monkeypatch):
    session = make_session(ruleset_id="coc7_lite")
    rolls = iter([5, 8, 2])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))

    result = resolve_check_request(
        session,
        {
            "type": "san_check",
            "actor": "艾莉丝",
            "success_loss": "0",
            "failure_loss": "1d4",
        },
    )

    assert result.success is False
    assert result.total == 85
    assert result.state_patches == [
        {
            "target": "pc:艾莉丝",
            "op": "san_delta",
            "value": -3,
            "reason": "SAN check failure_loss 1d4",
        }
    ]


def test_ruleset_state_patches_handle_common_semistrict_ops():
    session = make_session()
    pc = session.players["u1"]

    damage = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "damage", "value": 3},
    )
    heal = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "heal", "value": 2},
    )
    resource = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "resource_delta", "field": "mp", "value": -2},
    )
    skill = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "skill_delta", "field": "侦查", "value": 5},
    )
    skipped = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "unknown", "value": 1},
    )

    assert pc.hp == 9
    assert pc.ruleset_data["mp"] == 8
    assert pc.skills["侦查"] == 60
    assert [damage.applied, heal.applied, resource.applied, skill.applied] == [
        True,
        True,
        True,
        True,
    ]
    assert skipped.applied is False


def test_ruleset_state_patches_reject_negative_damage_and_heal():
    session = make_session()
    pc = session.players["u1"]
    initial_hp = pc.hp

    damage = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "damage", "value": -3},
    )
    heal = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "heal", "value": -2},
    )

    assert damage.applied is False
    assert heal.applied is False
    assert pc.hp == initial_hp


def test_ruleset_state_patches_reject_non_integer_values():
    session = make_session()
    pc = session.players["u1"]
    initial_hp = pc.hp
    initial_mp = pc.ruleset_data["mp"]
    initial_skill = pc.skills["侦查"]

    damage = apply_ruleset_state_patch(
        session,
        {"target": "pc:艾莉丝", "op": "damage", "value": "many"},
    )
    resource = apply_ruleset_state_patch(
        session,
        {
            "target": "pc:艾莉丝",
            "op": "resource_delta",
            "field": "mp",
            "value": "many",
        },
    )
    skill = apply_ruleset_state_patch(
        session,
        {
            "target": "pc:艾莉丝",
            "op": "skill_delta",
            "field": "侦查",
            "value": "many",
        },
    )

    assert [damage.applied, resource.applied, skill.applied] == [False, False, False]
    assert pc.hp == initial_hp
    assert pc.ruleset_data["mp"] == initial_mp
    assert pc.skills["侦查"] == initial_skill
