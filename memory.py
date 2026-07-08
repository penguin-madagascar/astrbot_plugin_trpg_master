from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

try:
    from .models import (
        GameSession,
        KnowledgeClue,
        KnowledgeEntity,
        KnowledgeFact,
        KnowledgeRelationship,
        KnowledgeThread,
        TimelineEvent,
    )
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import (
        GameSession,
        KnowledgeClue,
        KnowledgeEntity,
        KnowledgeFact,
        KnowledgeRelationship,
        KnowledgeThread,
        TimelineEvent,
    )


ALLOWED_VISIBILITIES = {"public", "private", "gm_only"}
ALLOWED_STATUSES = {"active", "resolved", "obsolete"}
ALLOWED_CLUE_STATUSES = {"hidden", "available", "discovered", "resolved"}
ALLOWED_THREAD_STATUSES = {"active", "resolved", "abandoned"}
ALLOWED_KNOWLEDGE_OPS = {
    "add_fact",
    "update_entity",
    "add_timeline_event",
    "update_clue",
    "update_thread",
    "set_relationship",
}


@dataclass(frozen=True)
class KnowledgeApplyResult:
    applied: bool
    op: str
    message: str


@dataclass(frozen=True)
class _MemoryCandidate:
    score: int
    text: str
    turn: int


def apply_knowledge_patches(
    session: GameSession,
    patches: list[dict[str, Any]],
) -> list[KnowledgeApplyResult]:
    results: list[KnowledgeApplyResult] = []
    for patch in patches or []:
        op = str(patch.get("op") or "")
        if op not in ALLOWED_KNOWLEDGE_OPS:
            results.append(_skip(op, "unsupported op"))
            continue
        try:
            result = _apply_knowledge_patch(session, op, patch)
        except ValueError as exc:
            result = _skip(op, str(exc))
        results.append(result)
    return results


def record_turn_timeline_event(
    session: GameSession,
    *,
    actor: str,
    action: str,
    outcome: str,
    visibility: str = "public",
    importance: int = 3,
) -> TimelineEvent:
    entry = TimelineEvent(
        event_id=_new_id(),
        summary=f"{actor}: {action} -> {_one_line(outcome, 180)}",
        visibility=_visibility(visibility),
        importance=_importance(importance),
        status="active",
        turn=session.turn_count,
        scene=_scene(session),
        entities=[actor] if actor else [],
        tags=[],
        source="turn",
    )
    session.campaign_knowledge.timeline.append(entry)
    return entry


def compact_campaign_knowledge(
    session: GameSession,
    *,
    max_timeline: int,
) -> None:
    knowledge = session.campaign_knowledge
    limit = max(1, int(max_timeline))
    if len(knowledge.timeline) <= limit:
        return

    keep_ids = {
        entry.event_id
        for entry in knowledge.timeline
        if entry.importance >= 4 and entry.status == "active"
    }
    for entry in reversed(knowledge.timeline):
        if len(keep_ids) >= limit:
            break
        keep_ids.add(entry.event_id)

    kept = [entry for entry in knowledge.timeline if entry.event_id in keep_ids]
    archived = [entry for entry in knowledge.timeline if entry.event_id not in keep_ids]
    if archived:
        archived_text = "\n".join(f"- T{entry.turn}: {entry.summary}" for entry in archived)
        knowledge.archive_summary = "\n".join(
            part for part in (knowledge.archive_summary, archived_text) if part
        )
    knowledge.timeline = kept[-limit:]


def build_memory_context(
    session: GameSession,
    *,
    actor: str,
    action: str,
    visibility: str,
    limit: int = 12,
) -> str:
    candidates = _memory_candidates(session, actor=actor, action=action, visibility=visibility)
    if not candidates:
        return ""
    ordered = sorted(candidates, key=lambda item: (item.score, item.turn), reverse=True)
    lines = ["战役知识库："]
    lines.extend(f"- {item.text}" for item in ordered[:limit])
    return "\n".join(lines)


def search_campaign_memory(
    session: GameSession,
    *,
    query: str,
    visibility: str,
    limit: int = 12,
) -> list[str]:
    candidates = _memory_candidates(
        session,
        actor="",
        action=query,
        visibility=visibility,
    )
    return [
        item.text
        for item in sorted(candidates, key=lambda item: (item.score, item.turn), reverse=True)[
            :limit
        ]
    ]


def player_visible_clues(session: GameSession) -> list[KnowledgeClue]:
    return [
        clue
        for clue in session.campaign_knowledge.clues.values()
        if clue.visibility in {"public", "private"}
        and clue.status != "obsolete"
        and clue.clue_status in {"available", "discovered", "resolved"}
    ]


def format_campaign_recap(session: GameSession, *, visibility: str = "player") -> str:
    lines = ["战役回顾"]
    timeline = [
        entry
        for entry in session.campaign_knowledge.timeline
        if _visible(entry.visibility, visibility) and entry.status != "obsolete"
    ]
    if timeline:
        lines.append("时间线：")
        lines.extend(f"- T{entry.turn}: {entry.summary}" for entry in timeline[-8:])
    active_threads = [
        thread
        for thread in session.campaign_knowledge.threads.values()
        if _visible(thread.visibility, visibility) and thread.thread_status == "active"
    ]
    if active_threads:
        lines.append("进行中的剧情线：")
        lines.extend(f"- {thread.title}: {thread.summary}" for thread in active_threads)
    clues = player_visible_clues(session)
    if clues:
        lines.append("线索：")
        lines.extend(
            f"- {clue.title} [{clue.clue_status}]: {clue.detail}" for clue in clues
        )
    return "\n".join(lines)


def _apply_knowledge_patch(
    session: GameSession,
    op: str,
    patch: dict[str, Any],
) -> KnowledgeApplyResult:
    meta = _meta(session, patch)
    if op == "add_timeline_event":
        summary = _required_text(patch, "summary")
        session.campaign_knowledge.timeline.append(
            TimelineEvent(
                event_id=str(patch.get("event_id") or patch.get("id") or _new_id()),
                summary=summary,
                **meta,
            )
        )
        return _applied(op, "timeline event added")

    if op == "update_entity":
        name = str(patch.get("name") or "").strip()
        entity_id = str(patch.get("entity_id") or patch.get("id") or name or "").strip()
        if not entity_id:
            raise ValueError("entity_id or name is required")
        existing = session.campaign_knowledge.entities.get(entity_id)
        entity = KnowledgeEntity(
            entity_id=entity_id,
            name=name or (existing.name if existing else entity_id),
            kind=str(patch.get("kind") or (existing.kind if existing else "entity")),
            aliases=patch.get("aliases")
            if "aliases" in patch
            else (existing.aliases if existing else []),
            summary=str(
                patch.get("summary")
                if "summary" in patch
                else (existing.summary if existing else "")
            ),
            **meta,
        )
        session.campaign_knowledge.entities[entity_id] = entity
        return _applied(op, f"entity updated: {entity_id}")

    if op == "add_fact":
        text = _required_text(patch, "text")
        session.campaign_knowledge.facts.append(
            KnowledgeFact(
                fact_id=str(patch.get("fact_id") or patch.get("id") or _new_id()),
                text=text,
                **meta,
            )
        )
        return _applied(op, "fact added")

    if op == "update_clue":
        clue_id = str(patch.get("clue_id") or patch.get("id") or "").strip()
        title = str(patch.get("title") or "").strip()
        if not clue_id and not title:
            raise ValueError("clue_id or title is required")
        clue_id = clue_id or _stable_id("clue", title)
        clue_status = _choice(
            patch.get("clue_status", "available"),
            ALLOWED_CLUE_STATUSES,
            "invalid clue_status",
        )
        existing = session.campaign_knowledge.clues.get(clue_id)
        clue = KnowledgeClue(
            clue_id=clue_id,
            title=title or (existing.title if existing else clue_id),
            detail=str(
                patch.get("detail")
                if "detail" in patch
                else (existing.detail if existing else "")
            ),
            clue_status=clue_status,
            **meta,
        )
        session.campaign_knowledge.clues[clue_id] = clue
        return _applied(op, f"clue updated: {clue_id}")

    if op == "update_thread":
        thread_id = str(patch.get("thread_id") or patch.get("id") or "").strip()
        title = str(patch.get("title") or "").strip()
        if not thread_id and not title:
            raise ValueError("thread_id or title is required")
        thread_id = thread_id or _stable_id("thread", title)
        thread_status = _choice(
            patch.get("thread_status", "active"),
            ALLOWED_THREAD_STATUSES,
            "invalid thread_status",
        )
        existing = session.campaign_knowledge.threads.get(thread_id)
        thread = KnowledgeThread(
            thread_id=thread_id,
            title=title or (existing.title if existing else thread_id),
            summary=str(
                patch.get("summary")
                if "summary" in patch
                else (existing.summary if existing else "")
            ),
            thread_status=thread_status,
            **meta,
        )
        session.campaign_knowledge.threads[thread_id] = thread
        return _applied(op, f"thread updated: {thread_id}")

    if op == "set_relationship":
        source = _required_text(patch, "source")
        target = _required_text(patch, "target")
        description = _required_text(patch, "description")
        relationship_meta = dict(meta)
        relationship_meta["source_note"] = str(patch.get("source_note") or meta["source"])
        del relationship_meta["source"]
        session.campaign_knowledge.relationships.append(
            KnowledgeRelationship(
                relationship_id=str(
                    patch.get("relationship_id") or patch.get("id") or _new_id()
                ),
                source=source,
                target=target,
                description=description,
                **relationship_meta,
            )
        )
        return _applied(op, "relationship added")

    return _skip(op, "unsupported op")


def _memory_candidates(
    session: GameSession,
    *,
    actor: str,
    action: str,
    visibility: str,
) -> list[_MemoryCandidate]:
    query = f"{actor} {action} {_scene(session)}".lower()
    knowledge = session.campaign_knowledge
    candidates: list[_MemoryCandidate] = []
    candidates.extend(
        _candidate(
            entry.summary,
            visibility=entry.visibility,
            target_visibility=visibility,
            importance=entry.importance,
            turn=entry.turn,
            query=query,
            haystack=_haystack(entry.summary, entry.entities, entry.tags, entry.scene),
        )
        for entry in knowledge.timeline
        if entry.status != "obsolete"
    )
    candidates.extend(
        _candidate(
            f"{entity.name} ({entity.kind}): {entity.summary}",
            visibility=entity.visibility,
            target_visibility=visibility,
            importance=entity.importance,
            turn=entity.turn,
            query=query,
            haystack=_haystack(
                entity.name,
                entity.aliases,
                entity.summary,
                entity.entities,
                entity.tags,
                entity.scene,
            ),
        )
        for entity in knowledge.entities.values()
        if entity.status != "obsolete"
    )
    candidates.extend(
        _candidate(
            fact.text,
            visibility=fact.visibility,
            target_visibility=visibility,
            importance=fact.importance,
            turn=fact.turn,
            query=query,
            haystack=_haystack(fact.text, fact.entities, fact.tags, fact.scene),
        )
        for fact in knowledge.facts
        if fact.status != "obsolete"
    )
    candidates.extend(
        _candidate(
            f"{clue.title} [{clue.clue_status}]: {clue.detail}",
            visibility=clue.visibility,
            target_visibility=visibility,
            importance=clue.importance,
            turn=clue.turn,
            query=query,
            haystack=_haystack(clue.title, clue.detail, clue.entities, clue.tags, clue.scene),
        )
        for clue in knowledge.clues.values()
        if clue.status != "obsolete"
    )
    candidates.extend(
        _candidate(
            f"{thread.title} [{thread.thread_status}]: {thread.summary}",
            visibility=thread.visibility,
            target_visibility=visibility,
            importance=thread.importance,
            turn=thread.turn,
            query=query,
            haystack=_haystack(
                thread.title,
                thread.summary,
                thread.entities,
                thread.tags,
                thread.scene,
            ),
        )
        for thread in knowledge.threads.values()
        if thread.status != "obsolete"
    )
    candidates.extend(
        _candidate(
            f"{relationship.source} -> {relationship.target}: {relationship.description}",
            visibility=relationship.visibility,
            target_visibility=visibility,
            importance=relationship.importance,
            turn=relationship.turn,
            query=query,
            haystack=_haystack(
                relationship.source,
                relationship.target,
                relationship.description,
                relationship.entities,
                relationship.tags,
                relationship.scene,
            ),
        )
        for relationship in knowledge.relationships
        if relationship.status != "obsolete"
    )
    return [candidate for candidate in candidates if candidate is not None]


def _candidate(
    text: str,
    *,
    visibility: str,
    target_visibility: str,
    importance: int,
    turn: int,
    query: str,
    haystack: str,
) -> _MemoryCandidate | None:
    if not _visible(visibility, target_visibility):
        return None
    relevance = _relevance(query, haystack)
    return _MemoryCandidate(
        score=int(importance) * 100 + relevance,
        text=text,
        turn=int(turn or 0),
    )


def _meta(session: GameSession, patch: dict[str, Any]) -> dict[str, Any]:
    visibility = _visibility(patch.get("visibility", "public"))
    status = _choice(
        patch.get("status", "active"),
        ALLOWED_STATUSES,
        "invalid status",
    )
    return {
        "visibility": visibility,
        "importance": _importance(patch.get("importance", 3)),
        "status": status,
        "turn": int(patch.get("turn", session.turn_count) or 0),
        "scene": str(patch.get("scene") or _scene(session)),
        "entities": _string_list(patch.get("entities") or []),
        "tags": _string_list(patch.get("tags") or []),
        "source": str(patch.get("source") or "gm_patch"),
    }


def _visible(entry_visibility: str, target_visibility: str) -> bool:
    target = str(target_visibility or "player")
    if target == "gm":
        return entry_visibility in ALLOWED_VISIBILITIES
    if target == "public":
        return entry_visibility == "public"
    return entry_visibility in {"public", "private"}


def _visibility(value: Any) -> str:
    return _choice(value, ALLOWED_VISIBILITIES, "invalid visibility")


def _importance(value: Any) -> int:
    try:
        importance = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid importance") from exc
    if importance < 1 or importance > 5:
        raise ValueError("invalid importance")
    return importance


def _choice(value: Any, allowed: set[str], message: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in allowed:
        raise ValueError(message)
    return normalized


def _required_text(patch: dict[str, Any], key: str) -> str:
    value = str(patch.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _string_list(values: list[Any] | Any) -> list[str]:
    if isinstance(values, list):
        return [str(item) for item in values if str(item).strip()]
    if values is None:
        return []
    return [str(values)]


def _scene(session: GameSession) -> str:
    return str(session.scene.get("location") or session.scene.get("description") or "")


def _haystack(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _relevance(query: str, haystack: str) -> int:
    score = 0
    for token in _query_tokens(query):
        if token and token in haystack:
            score += 50 + min(len(token), 20)
    return score


def _query_tokens(query: str) -> list[str]:
    separators = "，。！？；：,.!?;:()[]{}<>/\\|"
    normalized = str(query or "").lower()
    for separator in separators:
        normalized = normalized.replace(separator, " ")
    return [token for token in normalized.split() if len(token) >= 2]


def _one_line(value: str, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _stable_id(prefix: str, value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    return f"{prefix}-{cleaned}" if cleaned else _new_id()


def _new_id() -> str:
    return uuid4().hex[:12]


def _applied(op: str, message: str) -> KnowledgeApplyResult:
    return KnowledgeApplyResult(applied=True, op=op, message=message)


def _skip(op: str, message: str) -> KnowledgeApplyResult:
    return KnowledgeApplyResult(applied=False, op=op, message=message)
