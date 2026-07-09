import asyncio

import dice
import main
from main import LLMTRPGPlugin
from models import GameSession, PlayerCharacter


def test_trpg_act_uses_d20_ruleset_for_advantage_checks(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return (
            "艾莉丝冲过塌陷的石桥。\n"
            "```json\n"
            '{"dice_requests":[{"type":"skill_check","actor":"艾莉丝",'
            '"skill":"STR","dc":20,"advantage":"advantage",'
            '"reason":"跨越断桥"}]}\n'
            "```"
        )

    rolls = iter([2, 19])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))
    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    session = make_session(ruleset_id="d20_lite")
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"strict_json_patch": True, "second_pass_resolution": False},
    )
    plugin.storage = FakeStorage(session)

    outputs = asyncio.run(
        _collect(plugin.trpg_act(FakeEvent(user_id="u1", sender_name="Dana"), "冲过断桥"))
    )

    assert "rolls=[3, 20]" in outputs[0]
    assert "total=22" in outputs[0]
    assert "success" in outputs[0]


def test_trpg_act_uses_coc7_ruleset_and_applies_generated_san_loss(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return (
            "艾莉丝看见井底的白色手臂。\n"
            "```json\n"
            '{"dice_requests":[{"type":"san_check","actor":"艾莉丝",'
            '"success_loss":"0","failure_loss":"1d4"}]}\n'
            "```"
        )

    rolls = iter([5, 8, 2])
    monkeypatch.setattr(dice.secrets, "randbelow", lambda sides: next(rolls))
    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    session = make_session(ruleset_id="coc7_lite")
    plugin = LLMTRPGPlugin(
        context=object(),
        config={"strict_json_patch": True, "second_pass_resolution": False},
    )
    plugin.storage = FakeStorage(session)

    outputs = asyncio.run(
        _collect(plugin.trpg_act(FakeEvent(user_id="u1", sender_name="Dana"), "凝视井底"))
    )

    assert "SAN target 50" in outputs[0]
    assert "total=85" in outputs[0]
    assert "failure" in outputs[0]
    assert "艾莉丝 SAN 50->47" in outputs[0]
    assert session.players["u1"].san == 47


def make_session(*, ruleset_id: str) -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="雾镇",
        theme="民俗恐怖",
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
        attributes={"STR": 14, "DEX": 12},
        skills={"侦查": 55},
    )
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
    def __init__(self, session: GameSession) -> None:
        self.session = session

    async def load_session(self, session_id: str) -> GameSession | None:
        return self.session

    async def save_session(self, session: GameSession) -> None:
        self.session = session


async def _collect(generator):
    results = []
    async for item in generator:
        results.append(item)
    return results
