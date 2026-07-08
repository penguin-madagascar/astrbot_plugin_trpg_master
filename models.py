from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_ATTRIBUTES = {
    "STR": 10,
    "DEX": 10,
    "CON": 10,
    "INT": 10,
    "WIS": 10,
    "CHA": 10,
}


def _normalized_attributes(values: dict[str, Any] | None) -> dict[str, int]:
    attrs = dict(DEFAULT_ATTRIBUTES)
    attrs.update({str(k).upper(): int(v) for k, v in (values or {}).items()})
    return attrs


def _normalized_skills(values: dict[str, Any] | None) -> dict[str, int]:
    return {str(k): int(v) for k, v in (values or {}).items()}


def _string_list(values: list[Any] | None) -> list[str]:
    return [str(item) for item in (values or [])]


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
