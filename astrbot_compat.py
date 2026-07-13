from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    from astrbot.api import AstrBotConfig, logger
    from astrbot.api.event import AstrMessageEvent, MessageChain, filter
    from astrbot.api.message_components import Image
    from astrbot.api.star import Context, Star, StarTools, register
    from astrbot.api.web import error_response, file_response, json_response, request
    from astrbot.core.star.filter.command import GreedyStr
except ModuleNotFoundError:  # pragma: no cover - local checks outside AstrBot.
    logger = logging.getLogger(__name__)
    AstrBotConfig = dict
    AstrMessageEvent = Any
    Context = Any
    GreedyStr = str
    request = None

    def json_response(data: Any):
        return data

    def error_response(message: str, status_code: int = 400):
        return {"status": "error", "message": message, "status_code": status_code}

    def file_response(
        path: str | Path,
        *,
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ):
        return {
            "path": str(path),
            "filename": filename or Path(path).name,
            "content_type": content_type,
        }

    class MessageChain(list):
        pass

    class Image:
        @staticmethod
        def fromFileSystem(path: str | Path) -> str:
            return str(path)

    class Star:
        def __init__(self, context: Any) -> None:
            self.context = context

    class StarTools:
        @staticmethod
        def get_data_dir(plugin_name: str | None = None) -> Path:
            return Path("data") / "plugin_data" / (
                plugin_name or "astrbot_plugin_trpg_master"
            )

    class _EventMessageType:
        ALL = "all"

    class _Filter:
        EventMessageType = _EventMessageType

        @staticmethod
        def command(*_args: Any, **_kwargs: Any):
            def decorator(func: Any) -> Any:
                return func

            return decorator

        @staticmethod
        def event_message_type(*_args: Any, **_kwargs: Any):
            def decorator(func: Any) -> Any:
                return func

            return decorator

    filter = _Filter()

    def register(*_args: Any, **_kwargs: Any):
        def decorator(cls: Any) -> Any:
            return cls

        return decorator
