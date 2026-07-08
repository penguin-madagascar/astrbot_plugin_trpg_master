from __future__ import annotations

import hashlib
import json
import logging
from inspect import isawaitable
from pathlib import Path
from typing import Any

try:
    from astrbot.api import logger
except ModuleNotFoundError:  # pragma: no cover - tests outside AstrBot.
    logger = logging.getLogger(__name__)

try:
    from .models import CharacterPreset, GameSession, ScenarioScript
except ImportError:  # pragma: no cover - direct import outside package.
    from models import CharacterPreset, GameSession, ScenarioScript


class SessionStorage:
    def __init__(self, context: Any, data_dir: Path) -> None:
        self.context = context
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.presets_dir = self.data_dir / "presets"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    async def load_session(self, session_id: str) -> GameSession | None:
        key = self._key(session_id)
        data = await self._kv_get(key)
        if data is None:
            data = self._file_get(session_id)
        if data is None:
            return None
        if isinstance(data, str):
            data = json.loads(data)
        return GameSession.from_dict(data)

    async def save_session(self, session: GameSession) -> None:
        key = self._key(session.session_id)
        data = session.to_dict()
        if not await self._kv_put(key, data):
            self._file_put(session.session_id, data)
            return
        self._file_put(session.session_id, data)

    async def load_saved_sessions(self) -> list[GameSession]:
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as file:
                sessions.append(GameSession.from_dict(json.load(file)))
        return sessions

    async def delete_session(self, session_id: str) -> None:
        await self._kv_put(self._key(session_id), None)
        path = self._file_path(session_id)
        if path.exists():
            path.unlink()

    async def load_presets(self, owner_id: str) -> dict[str, CharacterPreset]:
        key = self._preset_key(owner_id)
        data = await self._kv_get(key)
        if data is None:
            data = self._preset_file_get(owner_id)
        if data is None:
            return {}
        if isinstance(data, str):
            data = json.loads(data)
        return {
            str(name): CharacterPreset.from_dict(preset)
            for name, preset in data.items()
        }

    async def save_presets(
        self,
        owner_id: str,
        presets: dict[str, CharacterPreset],
    ) -> None:
        key = self._preset_key(owner_id)
        data = {name: preset.to_dict() for name, preset in presets.items()}
        if not await self._kv_put(key, data):
            self._preset_file_put(owner_id, data)
            return
        self._preset_file_put(owner_id, data)

    async def load_scenario_scripts(self) -> dict[str, ScenarioScript]:
        data = await self._kv_get(self._scenario_scripts_key())
        if data is None:
            data = self._scenario_scripts_file_get()
        if data is None:
            return {}
        if isinstance(data, str):
            data = json.loads(data)
        return {
            str(script_id): ScenarioScript.from_dict(script)
            for script_id, script in data.items()
        }

    async def save_scenario_scripts(
        self,
        scripts: dict[str, ScenarioScript],
    ) -> None:
        data = {script_id: script.to_dict() for script_id, script in scripts.items()}
        if not await self._kv_put(self._scenario_scripts_key(), data):
            self._scenario_scripts_file_put(data)
            return
        self._scenario_scripts_file_put(data)

    async def find_scenario_script(self, query: str) -> ScenarioScript | None:
        target = str(query or "").strip()
        if not target:
            return None
        scripts = await self.load_scenario_scripts()
        if target in scripts:
            return scripts[target]
        for script in scripts.values():
            if script.title == target:
                return script
        return None

    async def _kv_get(self, key: str) -> Any | None:
        getter = getattr(self.context, "get_kv_data", None)
        if not callable(getter):
            return None
        for args in ((key,), ("astrbot_plugin_trpg_master", key)):
            try:
                return await _maybe_await(getter(*args))
            except TypeError:
                continue
            except Exception as exc:
                logger.debug("TRPG KV load failed: %s", exc)
                return None
        return None

    async def _kv_put(self, key: str, data: Any) -> bool:
        putter = getattr(self.context, "put_kv_data", None)
        if not callable(putter):
            return False
        for args in ((key, data), ("astrbot_plugin_trpg_master", key, data)):
            try:
                await _maybe_await(putter(*args))
                return True
            except TypeError:
                continue
            except Exception as exc:
                logger.debug("TRPG KV save failed: %s", exc)
                return False
        return False

    def _file_get(self, session_id: str) -> dict[str, Any] | None:
        path = self._file_path(session_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _file_put(self, session_id: str, data: dict[str, Any]) -> None:
        path = self._file_path(session_id)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _file_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return self.sessions_dir / f"{digest}.json"

    def _preset_file_get(self, owner_id: str) -> dict[str, Any] | None:
        path = self._preset_file_path(owner_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _preset_file_put(self, owner_id: str, data: dict[str, Any]) -> None:
        path = self._preset_file_path(owner_id)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _preset_file_path(self, owner_id: str) -> Path:
        digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
        return self.presets_dir / f"{digest}.json"

    def _scenario_scripts_file_get(self) -> dict[str, Any] | None:
        path = self._scenario_scripts_file_path()
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _scenario_scripts_file_put(self, data: dict[str, Any]) -> None:
        path = self._scenario_scripts_file_path()
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _scenario_scripts_file_path(self) -> Path:
        return self.data_dir / "scenario_scripts.json"

    @staticmethod
    def _key(session_id: str) -> str:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return f"trpg_session:{digest}"

    @staticmethod
    def _preset_key(owner_id: str) -> str:
        digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
        return f"trpg_presets:{digest}"

    @staticmethod
    def _scenario_scripts_key() -> str:
        return "trpg_scenario_scripts"


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value
