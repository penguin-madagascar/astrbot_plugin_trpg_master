import asyncio

import main
from gm import parse_structured_patch
from main import LLMTRPGPlugin
from models import GameSession, PlayerCharacter
from memory import (
    apply_knowledge_patches,
    build_memory_context,
    compact_campaign_knowledge,
    record_turn_timeline_event,
)
from prompts import build_action_prompt


def test_old_session_deserialization_gets_empty_campaign_knowledge():
    session = GameSession.from_dict(
        {
            "session_id": "session-1",
            "title": "雾镇",
            "theme": "民俗恐怖",
            "language": "zh",
        }
    )

    assert session.campaign_knowledge.timeline == []
    assert session.campaign_knowledge.entities == {}
    assert session.campaign_knowledge.facts == []
    assert session.campaign_knowledge.clues == {}
    assert session.campaign_knowledge.threads == {}
    assert session.campaign_knowledge.archive_summary == ""
    assert "campaign_knowledge" in session.to_dict()

    restored = GameSession.from_dict(session.to_dict())

    assert restored.campaign_knowledge == session.campaign_knowledge


def test_apply_knowledge_patches_updates_all_supported_knowledge_types():
    session = make_session()

    results = apply_knowledge_patches(
        session,
        [
            {
                "op": "add_timeline_event",
                "summary": "玩家抵达祠堂，发现木门从内侧锁住。",
                "visibility": "public",
                "importance": 3,
                "entities": ["艾莉丝", "祠堂"],
                "tags": ["开场"],
            },
            {
                "op": "update_entity",
                "entity_id": "npc-caretaker",
                "name": "林守夜",
                "kind": "npc",
                "summary": "守夜人知道十年前火灾的真相。",
                "aliases": ["守夜人"],
                "visibility": "gm_only",
                "importance": 5,
                "tags": ["雾镇", "火灾"],
            },
            {
                "op": "add_fact",
                "text": "林守夜在火灾当晚看见钟楼亮起蓝光。",
                "visibility": "gm_only",
                "importance": 5,
                "entities": ["林守夜", "钟楼"],
                "tags": ["火灾"],
            },
            {
                "op": "update_clue",
                "clue_id": "stopped-clock",
                "title": "停摆钟楼",
                "detail": "钟楼指针停在三点十七分。",
                "clue_status": "discovered",
                "visibility": "public",
                "importance": 4,
                "entities": ["钟楼"],
            },
            {
                "op": "update_thread",
                "thread_id": "missing-children",
                "title": "失踪孩童",
                "summary": "雾中失踪的孩童可能与旧井有关。",
                "thread_status": "active",
                "visibility": "private",
                "importance": 4,
                "entities": ["旧井"],
            },
            {
                "op": "set_relationship",
                "source": "npc-caretaker",
                "target": "艾莉丝",
                "description": "林守夜欠艾莉丝一个人情。",
                "visibility": "private",
                "importance": 3,
            },
        ],
    )

    assert all(result.applied for result in results)
    assert session.campaign_knowledge.timeline[0].summary.startswith("玩家抵达祠堂")
    assert session.campaign_knowledge.entities["npc-caretaker"].aliases == ["守夜人"]
    assert session.campaign_knowledge.facts[0].text.startswith("林守夜在火灾当晚")
    assert session.campaign_knowledge.clues["stopped-clock"].clue_status == "discovered"
    assert session.campaign_knowledge.threads["missing-children"].thread_status == "active"
    assert session.campaign_knowledge.relationships[0].target == "艾莉丝"


def test_apply_knowledge_patches_rejects_unsafe_values():
    session = make_session()

    results = apply_knowledge_patches(
        session,
        [
            {"op": "delete_log", "target": "all"},
            {"op": "add_fact", "text": "x", "visibility": "spoiler"},
            {"op": "update_clue", "clue_id": "c1", "title": "x", "clue_status": "gone"},
        ],
    )

    assert [result.applied for result in results] == [False, False, False]
    assert session.campaign_knowledge.facts == []
    assert session.campaign_knowledge.clues == {}


def test_build_memory_context_filters_visibility_and_prefers_relevant_entries():
    session = make_session()
    apply_knowledge_patches(
        session,
        [
            {
                "op": "add_fact",
                "text": "钟楼地下有通往旧井的密道。",
                "visibility": "gm_only",
                "importance": 5,
                "entities": ["钟楼", "旧井"],
            },
            {
                "op": "update_clue",
                "clue_id": "stopped-clock",
                "title": "停摆钟楼",
                "detail": "钟楼指针停在三点十七分。",
                "clue_status": "discovered",
                "visibility": "public",
                "importance": 4,
                "entities": ["钟楼"],
            },
            {
                "op": "add_fact",
                "text": "村口石碑刻着陌生姓氏。",
                "visibility": "public",
                "importance": 2,
                "entities": ["村口"],
            },
        ],
    )

    player_context = build_memory_context(
        session,
        actor="艾莉丝",
        action="调查钟楼",
        visibility="player",
    )
    gm_context = build_memory_context(
        session,
        actor="GM",
        action="调查钟楼",
        visibility="gm",
    )

    assert "停摆钟楼" in player_context
    assert "密道" not in player_context
    assert "密道" in gm_context
    assert gm_context.index("停摆钟楼") < gm_context.index("村口石碑")


def test_record_turn_event_and_compaction_preserve_important_active_memory():
    session = make_session()
    apply_knowledge_patches(
        session,
        [
            {"op": "add_fact", "text": "旧井封印不能被破坏。", "importance": 5},
            {
                "op": "update_clue",
                "clue_id": "well-seal",
                "title": "旧井封印",
                "detail": "井口符文仍在发热。",
                "clue_status": "discovered",
                "importance": 5,
            },
        ],
    )
    for index in range(5):
        record_turn_timeline_event(
            session,
            actor="艾莉丝",
            action=f"调查区域 {index}",
            outcome=f"发现痕迹 {index}",
        )
    session.campaign_knowledge.timeline[0].importance = 5

    compact_campaign_knowledge(session, max_timeline=3)

    summaries = [entry.summary for entry in session.campaign_knowledge.timeline]
    assert any("调查区域 0" in summary for summary in summaries)
    assert len(session.campaign_knowledge.timeline) == 3
    assert "调查区域 1" in session.campaign_knowledge.archive_summary
    assert session.campaign_knowledge.facts[0].text == "旧井封印不能被破坏。"
    assert session.campaign_knowledge.clues["well-seal"].clue_status == "discovered"


def test_gm_patch_parser_keeps_knowledge_patches():
    parsed = parse_structured_patch(
        """
玩家推开门。
```json
{
  "knowledge_patches": [
    {"op": "add_fact", "text": "钟楼地下有密道。", "visibility": "gm_only"}
  ]
}
```
""",
        strict=True,
    )

    assert parsed.patch["knowledge_patches"] == [
        {"op": "add_fact", "text": "钟楼地下有密道。", "visibility": "gm_only"}
    ]


def test_action_prompt_uses_relevant_memory_context_instead_of_recent_event_dump():
    session = make_session()
    session.recent_events = [f"旧流水事件 {index}" for index in range(5)]
    apply_knowledge_patches(
        session,
        [
            {
                "op": "add_fact",
                "text": "钟楼地下有通往旧井的密道。",
                "visibility": "gm_only",
                "importance": 5,
                "entities": ["钟楼", "旧井"],
            }
        ],
    )

    prompt = build_action_prompt(session, "艾莉丝", "调查钟楼")

    assert "战役知识库" in prompt
    assert "钟楼地下有通往旧井的密道" in prompt
    assert "旧流水事件 0" not in prompt
    assert "knowledge_patches" in prompt


def test_trpg_act_applies_knowledge_patches_and_records_deterministic_timeline(monkeypatch):
    async def fake_call_gm(context, event, *, prompt, system_prompt):
        return """
艾莉丝注意到钟楼方向传来铜铃声。
```json
{
  "knowledge_patches": [
    {
      "op": "update_clue",
      "clue_id": "bell-sound",
      "title": "钟楼铃声",
      "detail": "铃声在无风时自行响起。",
      "clue_status": "discovered",
      "visibility": "public",
      "importance": 4,
      "entities": ["钟楼"]
    }
  ]
}
```
""".strip()

    monkeypatch.setattr(main, "call_gm", fake_call_gm)
    session = make_session()
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Dana",
        character_name="艾莉丝",
        concept="调查员",
    )
    plugin = LLMTRPGPlugin(context=object(), config={"strict_json_patch": True})
    plugin.storage = FakeStorage(session=session)

    outputs = asyncio.run(
        _collect(plugin.trpg_act(FakeEvent(user_id="u1", sender_name="Dana"), "调查钟楼"))
    )

    assert outputs == ["艾莉丝注意到钟楼方向传来铜铃声。"]
    assert session.campaign_knowledge.clues["bell-sound"].title == "钟楼铃声"
    assert any("调查钟楼" in entry.summary for entry in session.campaign_knowledge.timeline)


def test_memory_query_commands_do_not_expose_gm_only_entries():
    session = make_session()
    apply_knowledge_patches(
        session,
        [
            {
                "op": "add_fact",
                "text": "钟楼地下有通往旧井的密道。",
                "visibility": "gm_only",
                "importance": 5,
                "entities": ["钟楼"],
            },
            {
                "op": "update_clue",
                "clue_id": "stopped-clock",
                "title": "停摆钟楼",
                "detail": "钟楼指针停在三点十七分。",
                "clue_status": "discovered",
                "visibility": "public",
                "importance": 4,
                "entities": ["钟楼"],
            },
            {
                "op": "update_thread",
                "thread_id": "fog",
                "title": "雾镇真相",
                "summary": "浓雾正在扩大。",
                "thread_status": "active",
                "visibility": "private",
                "importance": 3,
            },
        ],
    )
    plugin = LLMTRPGPlugin(context=object())
    plugin.storage = FakeStorage(session=session)
    event = FakeEvent(user_id="u1", sender_name="Dana")

    recap = asyncio.run(_collect(plugin.trpg_recap(event)))
    memory = asyncio.run(_collect(plugin.trpg_memory(event, "钟楼")))
    clues = asyncio.run(_collect(plugin.trpg_clues(event)))

    assert "密道" not in recap[0]
    assert "密道" not in memory[0]
    assert "密道" not in clues[0]
    assert "停摆钟楼" in memory[0]
    assert "停摆钟楼" in clues[0]
    assert "雾镇真相" in recap[0]


def make_session() -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="雾镇",
        theme="民俗恐怖",
        language="zh",
    )
    session.scene["location"] = "祠堂"
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
