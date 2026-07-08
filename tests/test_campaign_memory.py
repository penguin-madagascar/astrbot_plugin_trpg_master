from models import GameSession
from memory import (
    apply_knowledge_patches,
    build_memory_context,
    compact_campaign_knowledge,
    record_turn_timeline_event,
)


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


def make_session() -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="雾镇",
        theme="民俗恐怖",
        language="zh",
    )
    session.scene["location"] = "祠堂"
    return session
