from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

try:
    from astrbot.api import logger
except ModuleNotFoundError:  # pragma: no cover - tests outside AstrBot.
    logger = logging.getLogger(__name__)


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.I | re.S)


@dataclass(frozen=True)
class ParsedGMResponse:
    narrative: str
    patch: dict[str, Any]


async def call_gm(
    context: Any,
    event: Any,
    *,
    prompt: str,
    system_prompt: str,
) -> str:
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "system_prompt": system_prompt,
    }
    provider_id = await resolve_provider_id(context, event)
    if provider_id:
        kwargs["chat_provider_id"] = provider_id
    response = await context.llm_generate(**kwargs)
    return str(getattr(response, "completion_text", "") or "").strip()


async def call_command_agent(
    context: Any,
    event: Any,
    *,
    prompt: str,
    system_prompt: str,
) -> str:
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "system_prompt": system_prompt,
    }
    provider_id = await resolve_provider_id(context, event)
    if provider_id:
        kwargs["chat_provider_id"] = provider_id
    response = await context.llm_generate(**kwargs)
    return parse_command_agent_response(
        str(getattr(response, "completion_text", "") or "")
    )


async def resolve_provider_id(context: Any, event: Any) -> str:
    getter = getattr(context, "get_current_chat_provider_id", None)
    if not callable(getter):
        return ""
    try:
        return str(await getter(umo=getattr(event, "unified_msg_origin", "")) or "")
    except TypeError:
        try:
            return str(await getter(getattr(event, "unified_msg_origin", "")) or "")
        except Exception as exc:
            logger.debug("TRPG provider id lookup failed: %s", exc)
            return ""
    except Exception as exc:
        logger.debug("TRPG provider id lookup failed: %s", exc)
        return ""


def parse_structured_patch(text: str, *, strict: bool = True) -> ParsedGMResponse:
    content = text or ""
    match = JSON_BLOCK_RE.search(content)
    if match:
        payload = match.group(1)
        narrative = (content[: match.start()] + content[match.end() :]).strip()
    elif strict:
        raise ValueError("GM response did not contain a JSON fenced block")
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("GM response did not contain a JSON object")
        payload = content[start : end + 1]
        narrative = (content[:start] + content[end + 1 :]).strip()

    patch = json.loads(payload)
    if not isinstance(patch, dict):
        raise ValueError("GM patch must be a JSON object")
    return ParsedGMResponse(narrative=narrative, patch=normalize_patch(patch))


def parse_command_agent_response(text: str) -> str:
    content = str(text or "").strip()
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("command agent response must be a JSON object")
    if "command_line" not in data:
        raise ValueError("command agent response missing command_line")
    return str(data.get("command_line") or "").strip()


def normalize_patch(patch: dict[str, Any]) -> dict[str, Any]:
    return {
        "dice_requests": _list_of_dicts(patch.get("dice_requests")),
        "state_patches": _list_of_dicts(patch.get("state_patches")),
        "scene_patch": patch.get("scene_patch")
        if isinstance(patch.get("scene_patch"), dict)
        else {},
        "knowledge_patches": _list_of_dicts(patch.get("knowledge_patches")),
        "new_plot_threads": [str(item) for item in patch.get("new_plot_threads", [])],
        "memory_notes": [str(item) for item in patch.get("memory_notes", [])],
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
