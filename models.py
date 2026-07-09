from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


DEFAULT_ATTRIBUTES = {
    "STR": 10,
    "DEX": 10,
    "CON": 10,
    "INT": 10,
    "WIS": 10,
    "CHA": 10,
}

TURN_ORDER_MODES = {"soft", "llm_gm"}
TURN_ORDER_PHASES = {"free", "turn_order", "paused"}


def _normalized_attributes(values: dict[str, Any] | None) -> dict[str, int]:
    attrs = dict(DEFAULT_ATTRIBUTES)
    attrs.update({str(k).upper(): int(v) for k, v in (values or {}).items()})
    return attrs


def _normalized_skills(values: dict[str, Any] | None) -> dict[str, int]:
    return {str(k): int(v) for k, v in (values or {}).items()}


def _string_list(values: list[Any] | None) -> list[str]:
    return [str(item) for item in (values or [])]


def normalize_turn_order_mode(value: Any, default: str = "llm_gm") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in TURN_ORDER_MODES:
        return normalized
    return default if default in TURN_ORDER_MODES else "llm_gm"


def normalize_turn_order_phase(value: Any, mode: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in TURN_ORDER_PHASES:
        return normalized
    return "turn_order" if mode == "soft" else "free"


def _knowledge_importance(value: Any, default: int = 3) -> int:
    try:
        importance = int(value)
    except (TypeError, ValueError):
        importance = default
    return min(5, max(1, importance))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlayerCharacter:
    user_id: str
    display_name: str
    character_name: str
    concept: str
    hp: int = 10
    san: int = 50
    attributes: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_ATTRIBUTES))
    skills: dict[str, int] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    status_effects: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerCharacter":
        payload = dict(data)
        payload["attributes"] = _normalized_attributes(payload.get("attributes"))
        payload["skills"] = _normalized_skills(payload.get("skills"))
        payload["inventory"] = _string_list(payload.get("inventory"))
        payload["status_effects"] = _string_list(payload.get("status_effects"))
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CharacterPreset:
    name: str
    character_name: str
    concept: str
    hp: int = 10
    san: int = 50
    attributes: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_ATTRIBUTES))
    skills: dict[str, int] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    status_effects: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.character_name = str(self.character_name or self.name)
        self.concept = str(self.concept)
        self.hp = int(self.hp)
        self.san = int(self.san)
        self.attributes = _normalized_attributes(self.attributes)
        self.skills = _normalized_skills(self.skills)
        self.inventory = _string_list(self.inventory)
        self.status_effects = _string_list(self.status_effects)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterPreset":
        payload = dict(data)
        name = str(payload.get("name") or payload.get("character_name") or "")
        return cls(
            name=name,
            character_name=str(payload.get("character_name") or name),
            concept=str(payload.get("concept") or ""),
            hp=int(payload.get("hp", 10)),
            san=int(payload.get("san", 50)),
            attributes=payload.get("attributes") or {},
            skills=payload.get("skills") or {},
            inventory=payload.get("inventory") or [],
            status_effects=payload.get("status_effects") or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_player_character(
        self,
        *,
        user_id: str,
        display_name: str,
    ) -> PlayerCharacter:
        return PlayerCharacter(
            user_id=user_id,
            display_name=display_name,
            character_name=self.character_name,
            concept=self.concept,
            hp=self.hp,
            san=self.san,
            attributes=dict(self.attributes),
            skills=dict(self.skills),
            inventory=list(self.inventory),
            status_effects=list(self.status_effects),
        )


@dataclass
class TurnOrderState:
    enabled: bool = False
    mode: str = "soft"
    phase: str = ""
    queue: list[str] = field(default_factory=list)
    current_index: int = 0
    round_count: int = 1
    paused: bool = False
    control_note: str = ""

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        self.mode = normalize_turn_order_mode(self.mode, default="llm_gm")
        self.phase = normalize_turn_order_phase(self.phase, self.mode)
        self.queue = _string_list(self.queue)
        self.current_index = max(0, int(self.current_index or 0))
        self.round_count = max(1, int(self.round_count or 1))
        self.paused = bool(self.paused)
        if self.phase == "paused":
            self.paused = True
        elif self.paused:
            self.phase = "paused"
        self.control_note = str(self.control_note or "").strip()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TurnOrderState":
        payload = dict(data or {})
        return cls(
            enabled=bool(payload.get("enabled", False)),
            mode=str(payload.get("mode") or "soft"),
            phase=str(payload.get("phase") or ""),
            queue=payload.get("queue") or [],
            current_index=int(payload.get("current_index", 0) or 0),
            round_count=int(payload.get("round_count", 1) or 1),
            paused=bool(payload.get("paused", False)),
            control_note=str(payload.get("control_note") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioScript:
    script_id: str
    title: str
    language: str = "zh"
    theme: str = ""
    summary: str = ""
    background: str = ""
    opening_scene: str = ""
    hooks: list[str] = field(default_factory=list)
    gm_notes: str = ""
    tags: list[str] = field(default_factory=list)
    turn_order_mode: str = "llm_gm"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.title = str(self.title).strip()
        self.script_id = str(self.script_id or _new_script_id()).strip()
        self.language = str(self.language or "zh").strip() or "zh"
        self.theme = str(self.theme or self.title).strip()
        self.summary = str(self.summary or "").strip()
        self.background = str(self.background or "").strip()
        self.opening_scene = str(self.opening_scene or "").strip()
        self.hooks = _string_list(self.hooks)
        self.gm_notes = str(self.gm_notes or "").strip()
        self.tags = _string_list(self.tags)
        self.turn_order_mode = normalize_turn_order_mode(self.turn_order_mode)
        self.created_at = str(self.created_at or utc_now_iso())
        self.updated_at = str(self.updated_at or self.created_at or utc_now_iso())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioScript":
        payload = dict(data)
        title = str(payload.get("title") or payload.get("theme") or "未命名剧本")
        created_at = str(payload.get("created_at") or utc_now_iso())
        return cls(
            script_id=str(payload.get("script_id") or payload.get("id") or _new_script_id()),
            title=title,
            language=str(payload.get("language") or "zh"),
            theme=str(payload.get("theme") or title),
            summary=str(payload.get("summary") or ""),
            background=str(payload.get("background") or ""),
            opening_scene=str(payload.get("opening_scene") or ""),
            hooks=payload.get("hooks") or [],
            gm_notes=str(payload.get("gm_notes") or ""),
            tags=payload.get("tags") or [],
            turn_order_mode=str(payload.get("turn_order_mode") or "llm_gm"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_session_context(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "title": self.title,
            "summary": self.summary,
            "background": self.background,
            "opening_scene": self.opening_scene,
            "hooks": list(self.hooks),
            "gm_notes": self.gm_notes,
            "tags": list(self.tags),
            "turn_order_mode": self.turn_order_mode,
        }


@dataclass
class NPC:
    name: str
    role: str = ""
    description: str = ""
    status: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NPC":
        return cls(**dict(data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiceResult:
    expression: str
    rolls: list[int]
    modifier: int
    total: int


@dataclass(frozen=True)
class D20CheckResult:
    attribute_value: int
    dc: int
    roll: int
    attribute_modifier: int
    total: int
    success: bool
    natural: str = ""


@dataclass
class SessionLogEntry:
    timestamp: str
    user: str
    command: str
    input: str
    output_summary: str

    @classmethod
    def new(
        cls,
        *,
        user: str,
        command: str,
        input_text: str,
        output_summary: str,
    ) -> "SessionLogEntry":
        return cls(
            timestamp=utc_now_iso(),
            user=user,
            command=command,
            input=input_text,
            output_summary=output_summary,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionLogEntry":
        return cls(**dict(data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimelineEvent:
    event_id: str
    summary: str
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        self.event_id = str(self.event_id or _new_knowledge_id()).strip()
        self.summary = str(self.summary or "").strip()
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source = str(self.source or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineEvent":
        payload = dict(data)
        return cls(
            event_id=str(payload.get("event_id") or payload.get("id") or ""),
            summary=str(payload.get("summary") or payload.get("text") or ""),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source=str(payload.get("source") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeEntity:
    entity_id: str
    name: str
    kind: str = "entity"
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        self.entity_id = str(self.entity_id or _new_knowledge_id()).strip()
        self.name = str(self.name or self.entity_id).strip()
        self.kind = str(self.kind or "entity").strip()
        self.aliases = _string_list(self.aliases)
        self.summary = str(self.summary or "").strip()
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source = str(self.source or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEntity":
        payload = dict(data)
        return cls(
            entity_id=str(payload.get("entity_id") or payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            kind=str(payload.get("kind") or "entity"),
            aliases=payload.get("aliases") or [],
            summary=str(payload.get("summary") or ""),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source=str(payload.get("source") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeFact:
    fact_id: str
    text: str
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        self.fact_id = str(self.fact_id or _new_knowledge_id()).strip()
        self.text = str(self.text or "").strip()
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source = str(self.source or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeFact":
        payload = dict(data)
        return cls(
            fact_id=str(payload.get("fact_id") or payload.get("id") or ""),
            text=str(payload.get("text") or ""),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source=str(payload.get("source") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeClue:
    clue_id: str
    title: str
    detail: str = ""
    clue_status: str = "available"
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        self.clue_id = str(self.clue_id or _new_knowledge_id()).strip()
        self.title = str(self.title or self.clue_id).strip()
        self.detail = str(self.detail or "").strip()
        self.clue_status = str(self.clue_status or "available")
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source = str(self.source or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeClue":
        payload = dict(data)
        return cls(
            clue_id=str(payload.get("clue_id") or payload.get("id") or ""),
            title=str(payload.get("title") or ""),
            detail=str(payload.get("detail") or ""),
            clue_status=str(payload.get("clue_status") or "available"),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source=str(payload.get("source") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeThread:
    thread_id: str
    title: str
    summary: str = ""
    thread_status: str = "active"
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        self.thread_id = str(self.thread_id or _new_knowledge_id()).strip()
        self.title = str(self.title or self.thread_id).strip()
        self.summary = str(self.summary or "").strip()
        self.thread_status = str(self.thread_status or "active")
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source = str(self.source or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeThread":
        payload = dict(data)
        return cls(
            thread_id=str(payload.get("thread_id") or payload.get("id") or ""),
            title=str(payload.get("title") or ""),
            summary=str(payload.get("summary") or ""),
            thread_status=str(payload.get("thread_status") or "active"),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source=str(payload.get("source") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeRelationship:
    relationship_id: str
    source: str
    target: str
    description: str
    visibility: str = "public"
    importance: int = 3
    status: str = "active"
    turn: int = 0
    scene: str = ""
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_note: str = ""

    def __post_init__(self) -> None:
        self.relationship_id = str(self.relationship_id or _new_knowledge_id()).strip()
        self.source = str(self.source or "").strip()
        self.target = str(self.target or "").strip()
        self.description = str(self.description or "").strip()
        self.visibility = str(self.visibility or "public")
        self.importance = _knowledge_importance(self.importance)
        self.status = str(self.status or "active")
        self.turn = int(self.turn or 0)
        self.scene = str(self.scene or "")
        self.entities = _string_list(self.entities)
        self.tags = _string_list(self.tags)
        self.source_note = str(self.source_note or "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeRelationship":
        payload = dict(data)
        return cls(
            relationship_id=str(payload.get("relationship_id") or payload.get("id") or ""),
            source=str(payload.get("source") or ""),
            target=str(payload.get("target") or ""),
            description=str(payload.get("description") or ""),
            visibility=str(payload.get("visibility") or "public"),
            importance=payload.get("importance", 3),
            status=str(payload.get("status") or "active"),
            turn=int(payload.get("turn", 0) or 0),
            scene=str(payload.get("scene") or ""),
            entities=payload.get("entities") or [],
            tags=payload.get("tags") or [],
            source_note=str(payload.get("source_note") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignKnowledge:
    timeline: list[TimelineEvent] = field(default_factory=list)
    entities: dict[str, KnowledgeEntity] = field(default_factory=dict)
    facts: list[KnowledgeFact] = field(default_factory=list)
    clues: dict[str, KnowledgeClue] = field(default_factory=dict)
    threads: dict[str, KnowledgeThread] = field(default_factory=dict)
    relationships: list[KnowledgeRelationship] = field(default_factory=list)
    archive_summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CampaignKnowledge":
        payload = dict(data or {})
        return cls(
            timeline=[
                TimelineEvent.from_dict(item)
                for item in payload.get("timeline", [])
                if isinstance(item, dict)
            ],
            entities={
                str(entity_id): KnowledgeEntity.from_dict(entity)
                for entity_id, entity in payload.get("entities", {}).items()
                if isinstance(entity, dict)
            },
            facts=[
                KnowledgeFact.from_dict(item)
                for item in payload.get("facts", [])
                if isinstance(item, dict)
            ],
            clues={
                str(clue_id): KnowledgeClue.from_dict(clue)
                for clue_id, clue in payload.get("clues", {}).items()
                if isinstance(clue, dict)
            },
            threads={
                str(thread_id): KnowledgeThread.from_dict(thread)
                for thread_id, thread in payload.get("threads", {}).items()
                if isinstance(thread, dict)
            },
            relationships=[
                KnowledgeRelationship.from_dict(item)
                for item in payload.get("relationships", [])
                if isinstance(item, dict)
            ],
            archive_summary=str(payload.get("archive_summary") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline": [entry.to_dict() for entry in self.timeline],
            "entities": {
                entity_id: entity.to_dict()
                for entity_id, entity in self.entities.items()
            },
            "facts": [fact.to_dict() for fact in self.facts],
            "clues": {
                clue_id: clue.to_dict() for clue_id, clue in self.clues.items()
            },
            "threads": {
                thread_id: thread.to_dict()
                for thread_id, thread in self.threads.items()
            },
            "relationships": [
                relationship.to_dict() for relationship in self.relationships
            ],
            "archive_summary": self.archive_summary,
        }


@dataclass
class GameSession:
    session_id: str
    title: str
    theme: str
    language: str
    status: str = "running"
    turn_count: int = 0
    players: dict[str, PlayerCharacter] = field(default_factory=dict)
    npcs: dict[str, NPC] = field(default_factory=dict)
    scene: dict[str, Any] = field(default_factory=dict)
    plot_threads: list[str] = field(default_factory=list)
    global_items: list[str] = field(default_factory=list)
    history_summary: str = ""
    recent_events: list[str] = field(default_factory=list)
    logs: list[SessionLogEntry] = field(default_factory=list)
    scenario_script: dict[str, Any] | None = None
    turn_order: TurnOrderState = field(default_factory=TurnOrderState)
    campaign_knowledge: CampaignKnowledge = field(default_factory=CampaignKnowledge)

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        title: str,
        theme: str,
        language: str,
    ) -> "GameSession":
        return cls(
            session_id=session_id,
            title=title,
            theme=theme,
            language=language or "zh",
            scene={"location": "", "description": ""},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSession":
        payload = dict(data)
        payload["language"] = str(payload.get("language") or "zh")
        payload["players"] = {
            str(user_id): PlayerCharacter.from_dict(player)
            for user_id, player in payload.get("players", {}).items()
        }
        payload["npcs"] = {
            str(name): NPC.from_dict(npc) for name, npc in payload.get("npcs", {}).items()
        }
        payload["logs"] = [
            SessionLogEntry.from_dict(item) for item in payload.get("logs", [])
        ]
        payload.setdefault("global_items", payload.pop("inventory", []))
        scenario_script = payload.get("scenario_script")
        payload["scenario_script"] = (
            dict(scenario_script) if isinstance(scenario_script, dict) else None
        )
        payload["turn_order"] = TurnOrderState.from_dict(payload.get("turn_order"))
        payload["campaign_knowledge"] = CampaignKnowledge.from_dict(
            payload.get("campaign_knowledge")
        )
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "theme": self.theme,
            "language": self.language,
            "status": self.status,
            "turn_count": self.turn_count,
            "players": {
                user_id: player.to_dict() for user_id, player in self.players.items()
            },
            "npcs": {name: npc.to_dict() for name, npc in self.npcs.items()},
            "scene": self.scene,
            "plot_threads": list(self.plot_threads),
            "global_items": list(self.global_items),
            "history_summary": self.history_summary,
            "recent_events": list(self.recent_events),
            "logs": [entry.to_dict() for entry in self.logs],
            "scenario_script": dict(self.scenario_script) if self.scenario_script else None,
            "turn_order": self.turn_order.to_dict(),
            "campaign_knowledge": self.campaign_knowledge.to_dict(),
        }

    def add_log(
        self,
        *,
        user: str,
        command: str,
        input_text: str,
        output_summary: str,
    ) -> None:
        self.logs.append(
            SessionLogEntry.new(
                user=user,
                command=command,
                input_text=input_text,
                output_summary=output_summary,
            )
        )

    def player_by_character_name(self, character_name: str) -> PlayerCharacter | None:
        for player in self.players.values():
            if player.character_name == character_name:
                return player
        return None


def _new_script_id() -> str:
    return uuid4().hex[:12]


def _new_knowledge_id() -> str:
    return uuid4().hex[:12]
