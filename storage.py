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
    from .models import GameSession
except ImportError:  # pragma: no cover - direct import outside package.
    from models import GameSession


class SessionStorage:
    def __init__(self, context: Any, data_dir: Path) -> None:
        self.context = context
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

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

    async def delete_session(self, session_id: str) -> None:
        await self._kv_put(self._key(session_id), None)
        path = self._file_path(session_id)
        if path.exists():
            path.unlink()

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

    @staticmethod
    def _key(session_id: str) -> str:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return f"trpg_session:{digest}"


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value
