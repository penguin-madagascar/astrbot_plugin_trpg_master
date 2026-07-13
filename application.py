from __future__ import annotations

from typing import Any, Awaitable, Callable

try:
    from . import event_utils, presentation
    from .astrbot_compat import logger
    from .memory import compact_campaign_knowledge
    from .models import (
        GameSession,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
    )
    from .prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        SIMPLE_GM_SYSTEM_PROMPT,
        build_summary_prompt,
    )
    from .rules import resolve_check_request
    from .turn_order import current_turn_player, is_current_turn, is_turn_order_active
except ImportError:  # pragma: no cover - direct module loading outside package.
    import event_utils
    import presentation
    from astrbot_compat import logger
    from memory import compact_campaign_knowledge
    from models import (
        GameSession,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
    )
    from prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        SIMPLE_GM_SYSTEM_PROMPT,
        build_summary_prompt,
    )
    from rules import resolve_check_request
    from turn_order import current_turn_player, is_current_turn, is_turn_order_active


class TRPGRuntime:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    async def running_session(self, event: Any) -> GameSession | None:
        session = await self.owner.storage.load_session(event_utils.session_id(event))
        if not session or session.status != "running":
            return None
        if not session.language:
            session.language = str(self.owner.config.get("response_language") or "zh")
        session.play_mode = normalize_play_mode(
            getattr(session, "play_mode", "advanced"),
            default="advanced",
        )
        session.feature_flags = normalize_feature_flags(
            getattr(session, "feature_flags", {}) or {},
            play_mode=session.play_mode,
        )
        return session

    async def command_language(self, event: Any) -> str:
        session = await self.owner.storage.load_session(event_utils.session_id(event))
        if session and session.status == "running":
            return session.language or "zh"
        return "zh"

    def start_feature_flags(
        self,
        play_mode: str,
        script: ScenarioScript | None,
    ) -> dict[str, bool]:
        normalized_mode = normalize_play_mode(play_mode, default="advanced")
        source_flags = (
            script.feature_flags if script and normalized_mode == "custom" else {}
        )
        flags = normalize_feature_flags(source_flags, play_mode=normalized_mode)
        if normalized_mode == "advanced":
            flags["command_agent_enabled"] = event_utils.config_bool(
                self.owner.config, "command_agent_enabled", True
            )
            flags["turn_order_enabled"] = (
                True
                if script
                else event_utils.config_bool(
                    self.owner.config, "turn_order_enabled", True
                )
            )
            flags["state_patch_enabled"] = event_utils.config_bool(
                self.owner.config, "allow_state_patch", True
            )
            flags["second_pass_resolution_enabled"] = event_utils.config_bool(
                self.owner.config, "second_pass_resolution", True
            )
        return flags

    def session_feature_enabled(self, session: GameSession, key: str) -> bool:
        mode = normalize_play_mode(
            getattr(session, "play_mode", "advanced"),
            default="advanced",
        )
        flags = normalize_feature_flags(
            getattr(session, "feature_flags", {}) or {},
            play_mode=mode,
        )
        enabled = bool(flags.get(key, default_feature_flags(mode).get(key, True)))
        if mode != "advanced":
            return enabled
        config_keys = {
            "command_agent_enabled": "command_agent_enabled",
            "state_patch_enabled": "allow_state_patch",
            "second_pass_resolution_enabled": "second_pass_resolution",
        }
        config_key = config_keys.get(key)
        if config_key:
            return enabled and event_utils.config_bool(
                self.owner.config, config_key, True
            )
        return enabled

    def gm_system_prompt(self, session: GameSession | None = None) -> str:
        if session is not None and not self.session_feature_enabled(
            session, "structured_patch_enabled"
        ):
            return SIMPLE_GM_SYSTEM_PROMPT
        return str(
            self.owner.config.get("gm_system_prompt") or DEFAULT_GM_SYSTEM_PROMPT
        )

    def execute_dice_requests(
        self,
        session: GameSession,
        requests: list[dict[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        lines: list[str] = []
        state_patches: list[dict[str, Any]] = []
        for request in requests:
            result = resolve_check_request(session, request)
            lines.append(result.message)
            state_patches.extend(result.state_patches)
        return lines, state_patches

    def apply_scene_and_memory(
        self,
        session: GameSession,
        patch: dict[str, Any],
        *,
        include_memory: bool = True,
    ) -> None:
        scene_patch = patch.get("scene_patch") or {}
        if isinstance(scene_patch, dict):
            for key in ("location", "description"):
                value = scene_patch.get(key)
                if value:
                    session.scene[key] = str(value)
        if not include_memory:
            return
        session.plot_threads.extend(
            item for item in patch.get("new_plot_threads", []) if item
        )
        session.recent_events.extend(
            item for item in patch.get("memory_notes", []) if item
        )

    def finish_turn(
        self,
        session: GameSession,
        event: Any,
        action: str,
        output: str,
    ) -> None:
        session.turn_count += 1
        summary = (
            f"{event_utils.sender_name(event)}: {action} -> "
            f"{event_utils.one_line(output, 180)}"
        )
        session.recent_events.append(summary)
        session.add_log(
            user=event_utils.sender_label(event),
            command="trpg_act",
            input_text=action,
            output_summary=event_utils.one_line(output, 200),
        )

    async def trim_recent_events(
        self,
        session: GameSession,
        event: Any,
        call_gm: Callable[..., Awaitable[str]],
    ) -> None:
        limit = max(
            1,
            event_utils.safe_int(
                self.owner.config.get("max_recent_events"), 20
            ),
        )
        timeline_limit = event_utils.safe_int(
            self.owner.config.get("max_timeline_events"), 80
        )
        if not self.session_feature_enabled(session, "knowledge_enabled"):
            session.recent_events = session.recent_events[-limit:]
            return
        if len(session.recent_events) <= limit:
            compact_campaign_knowledge(session, max_timeline=timeline_limit)
            return
        try:
            summary = await call_gm(
                self.owner.context,
                event,
                prompt=build_summary_prompt(session),
                system_prompt=self.gm_system_prompt(session),
            )
            if summary:
                session.history_summary = summary
        except Exception:
            logger.warning("TRPG history summary update failed")
        session.recent_events = session.recent_events[-limit:]
        compact_campaign_knowledge(session, max_timeline=timeline_limit)

    def turn_order_warning(self, session: GameSession, user_id: str) -> str:
        if session.turn_order.mode != "soft":
            return ""
        if not is_turn_order_active(session) or is_current_turn(session, user_id):
            return ""
        player = current_turn_player(session)
        if player is None:
            return ""
        return presentation.message(
            session.language,
            "turn_out_of_order",
            current=player.character_name,
        )
