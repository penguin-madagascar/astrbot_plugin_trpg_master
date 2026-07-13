from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Image,
        MessageChain,
        Star,
        StarTools,
        error_response,
        file_response,
        filter,
        json_response,
        logger,
        register,
        request,
    )
except ImportError:  # pragma: no cover - direct module loading outside package.
    from astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Image,
        MessageChain,
        Star,
        StarTools,
        error_response,
        file_response,
        filter,
        json_response,
        logger,
        register,
        request,
    )

try:
    from . import event_utils
    from . import preset_commands
    from . import presentation
    from . import scenario_io
    from .dice import roll_dice
    from .dice_gif import generate_dice_roll_gif
    from .export import export_session_markdown
    from .gm import call_command_agent, call_gm, parse_structured_patch
    from .language import detect_language_from_theme
    from .memory import (
        apply_knowledge_patches,
        compact_campaign_knowledge,
        format_campaign_recap,
        player_visible_clues,
        record_turn_timeline_event,
        search_campaign_memory,
    )
    from .models import (
        CharacterPreset,
        GameSession,
        PlayerCharacter,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
        normalize_ruleset_id,
        normalize_turn_order_mode,
    )
    from .prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        SIMPLE_GM_SYSTEM_PROMPT,
        build_action_prompt,
        build_command_agent_prompt,
        build_opening_prompt,
        build_resolution_prompt,
        build_summary_prompt,
    )
    from .rules import resolve_check_request
    from .state import apply_state_patches
    from .storage import SessionStorage
    from .turn_order import (
        add_player_to_turn_order,
        apply_turn_controls,
        advance_turn_order,
        can_submit_action,
        can_finish_turn,
        current_turn_player,
        initialize_turn_order,
        is_current_turn,
        is_turn_order_active,
    )
except ImportError:  # pragma: no cover - direct module loading outside package.
    import event_utils
    import preset_commands
    import presentation
    import scenario_io
    from dice import roll_dice
    from dice_gif import generate_dice_roll_gif
    from export import export_session_markdown
    from gm import call_command_agent, call_gm, parse_structured_patch
    from language import detect_language_from_theme
    from memory import (
        apply_knowledge_patches,
        compact_campaign_knowledge,
        format_campaign_recap,
        player_visible_clues,
        record_turn_timeline_event,
        search_campaign_memory,
    )
    from models import (
        CharacterPreset,
        GameSession,
        PlayerCharacter,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
        normalize_ruleset_id,
        normalize_turn_order_mode,
    )
    from prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        SIMPLE_GM_SYSTEM_PROMPT,
        build_action_prompt,
        build_command_agent_prompt,
        build_opening_prompt,
        build_resolution_prompt,
        build_summary_prompt,
    )
    from rules import resolve_check_request
    from state import apply_state_patches
    from storage import SessionStorage
    from turn_order import (
        add_player_to_turn_order,
        apply_turn_controls,
        advance_turn_order,
        can_submit_action,
        can_finish_turn,
        current_turn_player,
        initialize_turn_order,
        is_current_turn,
        is_turn_order_active,
    )


PLUGIN_NAME = "astrbot_plugin_trpg_master"
PLUGIN_VERSION = "0.1.0"
PLUGIN_REPOSITORY = "https://github.com/penguin-madagascar/astrbot_plugin_trpg_master"
PLUGIN_DESCRIPTION = "LLM 驱动的 TRPG/跑团插件，Python 负责骰子、规则判定、状态和日志。"
COMMAND_AGENT_SYSTEM_PROMPT = (
    "你是 TRPG 命令转换 Agent。只输出 JSON object，字段只能包含 command_line。"
)




@register(
    PLUGIN_NAME,
    "jiangxingda",
    PLUGIN_DESCRIPTION,
    PLUGIN_VERSION,
    PLUGIN_REPOSITORY,
)
class LLMTRPGPlugin(Star):
    def __init__(
        self,
        context: Context,
        config: AstrBotConfig | dict | None = None,
    ) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME)).resolve()
        self.storage = SessionStorage(self, self.data_dir)
        self._register_web_apis()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def trpg_message_intercept(self, event: AstrMessageEvent):
        session = await self._running_session(event)
        if not session:
            return

        raw_message = event_utils.event_message_text(event)
        stripped = raw_message.strip()
        if stripped.startswith("/") and not stripped.lower().startswith("/trpg_"):
            return
        sender_id = event_utils.sender_id(event)
        is_direct_trpg_command = stripped.lower().startswith("/trpg_")
        command_agent_enabled = self._session_feature_enabled(
            session,
            "command_agent_enabled",
        )
        if (
            not is_direct_trpg_command
            and not command_agent_enabled
            and sender_id not in session.players
        ):
            return

        event_utils.block_default_llm(event)
        try:
            if not stripped:
                yield event.plain_result("无法处理空的跑团输入。")
                return
            if is_direct_trpg_command:
                async for item in self._dispatch_trpg_message_command(event, stripped):
                    yield item
                return
            if not command_agent_enabled:
                async for item in self.trpg_act(event, stripped):
                    yield item
                return

            try:
                command_line = await self._command_agent_command_line(
                    event,
                    session,
                    stripped,
                )
            except ValueError:
                logger.warning("TRPG command agent returned invalid JSON")
                yield event.plain_result("命令转换 Agent 返回无效 JSON。")
                return
            if not command_line:
                if not self._command_agent_action_allowed(session, sender_id):
                    yield event.plain_result("当前阶段不允许提交角色行动。")
                    return
                command_line = f"/trpg_act {stripped}"

            error = self._validate_command_agent_line(
                session,
                sender_id,
                command_line,
            )
            if error:
                yield event.plain_result(error)
                return
            async for item in self._dispatch_trpg_message_command(event, command_line):
                yield item
        except Exception:
            logger.exception("TRPG intercepted message handling failed")
            yield event.plain_result("跑团输入处理失败。")
        finally:
            event_utils.stop_event(event)

    @filter.command("trpg_help", desc="显示 LLM TRPG 插件帮助。")
    async def trpg_help(self, event: AstrMessageEvent):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            language = session.language if session and session.status == "running" else "zh"
            yield event.plain_result(presentation.help_text(language))
        except Exception:
            logger.exception("TRPG help failed")
            yield event.plain_result("TRPG 帮助生成失败。")

    @filter.command("trpg_start", desc="启动新的 LLM TRPG 跑团。")
    async def trpg_start(self, event: AstrMessageEvent, theme: GreedyStr = ""):
        session_id = event_utils.session_id(event)
        existing = await self.storage.load_session(session_id)
        if existing and existing.status == "running":
            yield event.plain_result(presentation.message(existing.language, "session_running"))
            return
        if existing:
            try:
                await self.storage.delete_session(session_id)
            except Exception:
                logger.exception("TRPG legacy session cleanup failed")
                yield event.plain_result(
                    presentation.message(existing.language, "start_cleanup_failed")
                )
                return

        raw_theme = str(theme or "").strip()
        requested_mode, script_query = event_utils.split_start_mode(raw_theme)
        default_theme = str(self.config.get("default_theme") or "奇幻冒险")
        script = (
            await self.storage.find_scenario_script(script_query)
            if script_query
            else None
        )
        play_mode = requested_mode or (script.play_mode if script else "simple")
        feature_flags = self._start_feature_flags(play_mode, script)
        session_title = script.title if script else (script_query or default_theme)
        session_theme = script.theme if script else session_title
        language = (
            script.language
            if script
            else detect_language_from_theme(script_query) if script_query else "zh"
        )
        ruleset_id = (
            script.ruleset_id
            if script
            else normalize_ruleset_id(self.config.get("default_ruleset_id") or "d20_lite")
        )
        session = GameSession.new(
            session_id=session_id,
            title=session_title,
            theme=session_theme,
            language=language,
            ruleset_id=ruleset_id,
            play_mode=play_mode,
            feature_flags=feature_flags,
        )
        turn_enabled = bool(feature_flags.get("turn_order_enabled", True))
        turn_mode = (
            script.turn_order_mode
            if script
            else normalize_turn_order_mode(self.config.get("turn_order_mode") or "llm_gm")
        )
        initialize_turn_order(
            session,
            enabled=turn_enabled,
            mode=turn_mode,
        )
        if script:
            session.scenario_script = script.to_session_context()
            session.scenario_script["play_mode"] = play_mode
            session.scenario_script["feature_flags"] = dict(feature_flags)
            session.history_summary = scenario_io.scenario_history_summary(script)
            session.scene["description"] = script.opening_scene
            session.plot_threads.extend(script.hooks)
            if feature_flags.get("knowledge_enabled", True):
                scenario_io.initialize_scenario_knowledge(session, script)

        try:
            opening = await call_gm(
                self.context,
                event,
                prompt=build_opening_prompt(session),
                system_prompt=self._gm_system_prompt(session),
            )
        except Exception:
            logger.exception("TRPG opening generation failed")
            opening = presentation.message(language, "started_fallback")

        session.scene["description"] = event_utils.one_line(opening, 500)
        session.recent_events.append(f"Session started: {session_theme}")
        session.add_log(
            user=event_utils.sender_label(event),
            command="trpg_start",
            input_text=session_theme,
            output_summary=event_utils.one_line(opening, 160),
        )
        await self.storage.save_session(session)
        yield event.plain_result(opening)

    @filter.command("trpg_join", desc="加入当前跑团并创建角色。")
    async def trpg_join(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            raw = str(query or "").strip()
            if not raw:
                yield event.plain_result(presentation.message(session.language, "join_usage"))
                return
            if raw.lower().startswith("preset:"):
                preset_name = raw[len("preset:") :].strip()
                if not preset_name:
                    yield event.plain_result(presentation.message(session.language, "join_usage"))
                    return
                user_id = event_utils.sender_id(event)
                presets = await self.storage.load_presets(user_id)
                preset = presets.get(preset_name)
                if preset is None:
                    yield event.plain_result(
                        presentation.message(session.language, "preset_not_found", name=preset_name)
                    )
                    return
                if preset.ruleset_id != session.ruleset_id:
                    yield event.plain_result(
                        presentation.message(
                            session.language,
                            "preset_ruleset_mismatch",
                            name=preset.name,
                            preset_ruleset=preset.ruleset_id,
                            session_ruleset=session.ruleset_id,
                        )
                    )
                    return
                pc = preset.to_player_character(
                    user_id=user_id,
                    display_name=event_utils.sender_name(event),
                )
                session.players[user_id] = pc
                add_player_to_turn_order(session, user_id)
                output = presentation.message(
                    session.language,
                    "joined",
                    name=pc.character_name,
                    hp=pc.hp,
                    san=pc.san,
                )
                session.add_log(
                    user=event_utils.sender_label(event),
                    command="trpg_join",
                    input_text=raw,
                    output_summary=output,
                )
                await self.storage.save_session(session)
                yield event.plain_result(output)
                return
            character_name, concept = event_utils.split_first(raw)
            if not character_name:
                yield event.plain_result(presentation.message(session.language, "join_usage"))
                return

            user_id = event_utils.sender_id(event)
            pc = PlayerCharacter(
                user_id=user_id,
                display_name=event_utils.sender_name(event),
                character_name=character_name,
                concept=concept,
                ruleset_id=session.ruleset_id,
            )
            session.players[user_id] = pc
            add_player_to_turn_order(session, user_id)
            output = presentation.message(
                session.language,
                "joined",
                name=pc.character_name,
                hp=pc.hp,
                san=pc.san,
            )
            session.add_log(
                user=event_utils.sender_label(event),
                command="trpg_join",
                input_text=raw,
                output_summary=output,
            )
            await self.storage.save_session(session)
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG join failed")
            yield event.plain_result("加入跑团失败，请稍后重试。")

    @filter.command("trpg_preset", desc="管理自己的 TRPG 角色预设。")
    async def trpg_preset(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            language = await self._command_language(event)
            raw = str(query or "").strip()
            action, rest = event_utils.split_first(raw)
            action = action.lower()
            if action == "create":
                output = await self._preset_create(event, language, rest)
                yield event.plain_result(output)
                return
            if action == "list":
                output = await self._preset_list(event, language)
                yield event.plain_result(output)
                return
            if action == "show":
                output = await self._preset_show(event, language, rest)
                yield event.plain_result(output)
                return
            if action == "update":
                output = await self._preset_update(event, language, rest)
                yield event.plain_result(output)
                return
            yield event.plain_result(presentation.message(language, "preset_usage"))
        except ValueError as exc:
            yield event.plain_result(str(exc))
        except Exception:
            logger.exception("TRPG preset command failed")
            yield event.plain_result("角色预设操作失败，请稍后重试。")

    @filter.command("trpg_pc", desc="查看自己的角色卡。")
    async def trpg_pc(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            pc = session.players.get(event_utils.sender_id(event))
            if not pc:
                yield event.plain_result(presentation.message(session.language, "not_joined"))
                return
            yield event.plain_result(presentation.format_pc(session.language, pc))
        except Exception:
            logger.exception("TRPG pc failed")
            yield event.plain_result("角色卡读取失败，请稍后重试。")

    @filter.command("trpg_status", desc="查看当前跑团状态。")
    async def trpg_status(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            yield event.plain_result(presentation.format_status(session))
        except Exception:
            logger.exception("TRPG status failed")
            yield event.plain_result("跑团状态读取失败，请稍后重试。")

    @filter.command("trpg_turn", desc="查看或管理当前跑团行动顺序。")
    async def trpg_turn(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if not session.turn_order.enabled:
                yield event.plain_result(presentation.message(session.language, "turn_disabled"))
                return

            raw = str(query or "").strip()
            action = event_utils.split_first(raw)[0].lower()
            sender_id = event_utils.sender_id(event)

            if not action:
                yield event.plain_result(presentation.format_turn_order(session))
                return
            if action in {"next", "done"}:
                if session.turn_order.mode == "llm_gm":
                    request_text = (
                        "请求结束当前行动。"
                        if action == "done"
                        else "请求推进到下一位行动者。"
                    )
                    async for item in self.trpg_act(event, request_text):
                        yield item
                    return
                if not can_finish_turn(session, sender_id):
                    yield event.plain_result(presentation.message(session.language, "turn_denied_done"))
                    return
                advance_turn_order(session)
                await self.storage.save_session(session)
                yield event.plain_result(presentation.turn_advanced_message(session))
                return

            yield event.plain_result(presentation.message(session.language, "turn_usage"))
        except Exception:
            logger.exception("TRPG turn command failed")
            yield event.plain_result("行动顺序操作失败，请稍后重试。")

    @filter.command("trpg_recap", desc="查看玩家可见的战役回顾。")
    async def trpg_recap(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            yield event.plain_result(format_campaign_recap(session, visibility="player"))
        except Exception:
            logger.exception("TRPG recap command failed")
            yield event.plain_result("战役回顾读取失败，请稍后重试。")

    @filter.command("trpg_memory", desc="搜索玩家可见的战役记忆。")
    async def trpg_memory(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            keyword = str(query or "").strip()
            if not keyword:
                yield event.plain_result(presentation.message(session.language, "memory_usage"))
                return
            results = search_campaign_memory(
                session,
                query=keyword,
                visibility="player",
            )
            if not results:
                yield event.plain_result(presentation.message(session.language, "memory_empty"))
                return
            output = f"{presentation.message(session.language, 'memory_title')}:\n" + "\n".join(
                f"- {item}" for item in results
            )
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG memory command failed")
            yield event.plain_result("战役记忆搜索失败，请稍后重试。")

    @filter.command("trpg_clues", desc="查看玩家可见线索。")
    async def trpg_clues(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            clues = player_visible_clues(session)
            if not clues:
                yield event.plain_result(presentation.message(session.language, "clues_empty"))
                return
            output = f"{presentation.message(session.language, 'clues_title')}:\n" + "\n".join(
                f"- {clue.title} [{clue.clue_status}]: {clue.detail}"
                for clue in clues
            )
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG clues command failed")
            yield event.plain_result("线索读取失败，请稍后重试。")

    @filter.command("trpg_act", desc="提交玩家行动并推进剧情。")
    async def trpg_act(self, event: AstrMessageEvent, action: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if event_utils.sender_id(event) not in session.players:
                yield event.plain_result(presentation.message(session.language, "member_required"))
                return
            raw_action = str(action or "").strip()
            if not raw_action:
                yield event.plain_result(presentation.message(session.language, "act_usage"))
                return
            if session.turn_count >= event_utils.safe_int(
                self.config.get("max_turns"), 200
            ):
                yield event.plain_result(presentation.message(session.language, "max_turns"))
                return

            sender_id = event_utils.sender_id(event)
            actor_pc = session.players.get(sender_id)
            actor = (
                actor_pc.character_name
                if actor_pc
                else event_utils.sender_name(event)
            )
            if not can_submit_action(session, sender_id):
                yield event.plain_result(
                    presentation.message(
                        session.language,
                        "turn_denied_action",
                        current=presentation.turn_current_label(session),
                    )
                )
                return
            turn_warning = self._turn_order_warning(session, sender_id)
            should_advance_turn = (
                session.turn_order.mode == "soft"
                and is_turn_order_active(session)
                and is_current_turn(session, sender_id)
            )
            raw_reply = await call_gm(
                self.context,
                event,
                prompt=build_action_prompt(session, actor, raw_action),
                system_prompt=self._gm_system_prompt(session),
            )

            if not self._session_feature_enabled(session, "structured_patch_enabled"):
                final = presentation.prepend_turn_warning(turn_warning, raw_reply.strip())
                self._finish_turn(session, event, raw_action, final)
                await self._trim_recent_events(session, event)
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            try:
                parsed = parse_structured_patch(
                    raw_reply,
                    strict=bool(self.config.get("strict_json_patch", True)),
                )
            except Exception:
                logger.warning("TRPG GM JSON parse failed")
                final = "\n\n".join(
                    part for part in (raw_reply.strip(), presentation.message(session.language, "json_failed")) if part
                )
                final = presentation.prepend_turn_warning(turn_warning, final)
                if self._session_feature_enabled(session, "knowledge_enabled"):
                    record_turn_timeline_event(
                        session,
                        actor=actor,
                        action=raw_action,
                        outcome=final,
                    )
                self._finish_turn(session, event, raw_action, final)
                if should_advance_turn:
                    advance_turn_order(session)
                await self._trim_recent_events(session, event)
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            if self._session_feature_enabled(session, "dice_requests_enabled"):
                dice_lines, dice_state_patches = self._execute_dice_requests(
                    session,
                    parsed.patch["dice_requests"],
                )
            else:
                dice_lines, dice_state_patches = [], []
            state_patches = [*dice_state_patches, *parsed.patch["state_patches"]]
            state_results = (
                apply_state_patches(session, state_patches)
                if self._session_feature_enabled(session, "state_patch_enabled")
                else []
            )
            if self._session_feature_enabled(session, "knowledge_enabled"):
                apply_knowledge_patches(session, parsed.patch["knowledge_patches"])
            turn_results = (
                apply_turn_controls(session, parsed.patch["turn_controls"])
                if self._session_feature_enabled(session, "turn_order_enabled")
                else []
            )
            self._apply_scene_and_memory(
                session,
                parsed.patch,
                include_memory=self._session_feature_enabled(session, "knowledge_enabled"),
            )

            dice_summary = "\n".join(dice_lines)
            state_summary = "\n".join(result.message for result in state_results)
            turn_summary = "\n".join(result.message for result in turn_results)
            resolution = ""
            if self._session_feature_enabled(session, "second_pass_resolution_enabled") and (
                dice_summary or state_summary
            ):
                try:
                    resolution = await call_gm(
                        self.context,
                        event,
                        prompt=build_resolution_prompt(
                            session,
                            parsed.narrative,
                            dice_summary,
                            state_summary,
                        ),
                        system_prompt=self._gm_system_prompt(session),
                    )
                except Exception:
                    logger.warning("TRPG second pass resolution failed")

            final = presentation.compose_action_output(
                session.language,
                parsed.narrative,
                dice_summary,
                state_summary,
                turn_summary,
                resolution,
            )
            final = presentation.prepend_turn_warning(turn_warning, final)
            if self._session_feature_enabled(session, "knowledge_enabled"):
                record_turn_timeline_event(
                    session,
                    actor=actor,
                    action=raw_action,
                    outcome=final,
                )
            self._finish_turn(session, event, raw_action, final)
            if should_advance_turn:
                advance_turn_order(session)
            await self._trim_recent_events(session, event)
            await self.storage.save_session(session)
            yield event.plain_result(final)
        except Exception:
            logger.exception("TRPG act failed")
            yield event.plain_result(presentation.message("zh", "gm_failed"))

    @filter.command("trpg_roll", desc="掷基础骰子表达式。")
    async def trpg_roll(self, event: AstrMessageEvent, expression: GreedyStr = ""):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            language = session.language if session and session.status == "running" else "zh"
            expr = str(expression or "").strip()
            try:
                result = roll_dice(expr)
            except Exception as exc:
                yield event.plain_result(presentation.message(language, "roll_failed", error=str(exc)))
                return

            output = presentation.format_roll_text(language, result)
            try:
                gif_path = generate_dice_roll_gif(result, self.data_dir / "dice_gifs")
                chain_result = getattr(event, "chain_result", None)
                if not callable(chain_result):
                    raise RuntimeError("current AstrBot event does not support chain_result")
                if session and session.status == "running":
                    session.add_log(
                        user=event_utils.sender_label(event),
                        command="trpg_roll",
                        input_text=expr,
                        output_summary=(
                            f"GIF {gif_path.name}; {event_utils.one_line(output, 160)}"
                        ),
                    )
                    await self.storage.save_session(session)
                yield chain_result(MessageChain([Image.fromFileSystem(str(gif_path))]))
                return
            except Exception as exc:
                logger.warning("TRPG dice GIF generation failed, using text fallback: %s", exc)

            if session and session.status == "running":
                session.add_log(
                    user=event_utils.sender_label(event),
                    command="trpg_roll",
                    input_text=expr,
                    output_summary=output,
                )
                await self.storage.save_session(session)
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG roll failed")
            yield event.plain_result("掷骰失败，请稍后重试。")
            return

    @filter.command("trpg_end", desc="结束当前跑团。")
    async def trpg_end(self, event: AstrMessageEvent):
        session = None
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if event_utils.sender_id(event) not in session.players:
                yield event.plain_result(presentation.message(session.language, "member_required"))
                return
            await self.storage.delete_session(session.session_id)
            yield event.plain_result(presentation.message(session.language, "ended"))
        except Exception:
            logger.exception("TRPG end failed")
            language = session.language if session else "zh"
            yield event.plain_result(presentation.message(language, "end_failed"))

    @filter.command("trpg_export", desc="导出当前跑团 Markdown 日志。")
    async def trpg_export(self, event: AstrMessageEvent):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if event_utils.sender_id(event) not in session.players:
                yield event.plain_result(presentation.message(session.language, "member_required"))
                return
            path = export_session_markdown(session, self.data_dir)
            output = presentation.message(session.language, "exported", path=str(path))
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG export failed")
            yield event.plain_result("导出跑团日志失败，请稍后重试。")

    async def _running_session(self, event: AstrMessageEvent) -> GameSession | None:
        session = await self.storage.load_session(event_utils.session_id(event))
        if not session or session.status != "running":
            return None
        if not session.language:
            session.language = str(self.config.get("response_language") or "zh")
        session.play_mode = normalize_play_mode(
            getattr(session, "play_mode", "advanced"),
            default="advanced",
        )
        session.feature_flags = normalize_feature_flags(
            getattr(session, "feature_flags", {}) or {},
            play_mode=session.play_mode,
        )
        return session

    async def _command_language(self, event: AstrMessageEvent) -> str:
        session = await self.storage.load_session(event_utils.session_id(event))
        if session and session.status == "running":
            return session.language or "zh"
        return "zh"

    def _start_feature_flags(
        self,
        play_mode: str,
        script: ScenarioScript | None,
    ) -> dict[str, bool]:
        normalized_mode = normalize_play_mode(play_mode, default="advanced")
        source_flags = script.feature_flags if script and normalized_mode == "custom" else {}
        flags = normalize_feature_flags(source_flags, play_mode=normalized_mode)
        if normalized_mode == "advanced":
            flags["command_agent_enabled"] = event_utils.config_bool(
                self.config,
                "command_agent_enabled",
                True,
            )
            flags["turn_order_enabled"] = (
                True
                if script
                else event_utils.config_bool(
                    self.config, "turn_order_enabled", True
                )
            )
            flags["state_patch_enabled"] = event_utils.config_bool(
                self.config,
                "allow_state_patch",
                True,
            )
            flags["second_pass_resolution_enabled"] = event_utils.config_bool(
                self.config,
                "second_pass_resolution",
                True,
            )
        return flags

    def _session_feature_enabled(
        self,
        session: GameSession,
        key: str,
    ) -> bool:
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
        if key == "command_agent_enabled":
            return enabled and event_utils.config_bool(
                self.config, "command_agent_enabled", True
            )
        if key == "state_patch_enabled":
            return enabled and event_utils.config_bool(
                self.config, "allow_state_patch", True
            )
        if key == "second_pass_resolution_enabled":
            return enabled and event_utils.config_bool(
                self.config, "second_pass_resolution", True
            )
        return enabled

    async def _command_agent_command_line(
        self,
        event: AstrMessageEvent,
        session: GameSession,
        user_text: str,
    ) -> str:
        sender_id = event_utils.sender_id(event)
        prompt = build_command_agent_prompt(
            session,
            sender_id=sender_id,
            sender_name=event_utils.sender_name(event),
            user_text=user_text,
            allowed_commands=self._command_agent_allowed_commands(session, sender_id),
        )
        return await call_command_agent(
            self.context,
            event,
            prompt=prompt,
            system_prompt=COMMAND_AGENT_SYSTEM_PROMPT,
        )

    def _command_agent_allowed_commands(
        self,
        session: GameSession,
        sender_id: str,
    ) -> dict[str, str]:
        commands = {
            "/trpg_help": "显示 TRPG 帮助。",
            "/trpg_status": "查看当前跑团状态。",
            "/trpg_recap": "查看玩家可见的战役回顾。",
            "/trpg_memory <关键词>": "搜索玩家可见的战役记忆。",
            "/trpg_clues": "查看玩家可见线索。",
            "/trpg_roll <表达式>": "掷基础骰子表达式。",
        }
        if sender_id not in session.players:
            commands.update(
                {
                    "/trpg_join <角色名> <一句话设定>": "加入当前跑团并创建角色。",
                    "/trpg_preset <子命令>": "管理自己的角色预设。",
                }
            )
            return commands

        commands["/trpg_pc"] = "查看自己的角色卡。"
        commands["/trpg_end"] = "结束当前跑团；仅在玩家明确要求结束时使用。"
        commands["/trpg_export"] = "导出当前跑团日志；仅在玩家明确要求导出时使用。"
        if self._command_agent_action_allowed(session, sender_id):
            commands["/trpg_act <行动内容>"] = "提交当前角色行动。"
        if is_turn_order_active(session) and is_current_turn(session, sender_id):
            commands["/trpg_turn done"] = "当前行动者结束自己的行动并推进顺序。"
            commands["/trpg_turn next"] = "当前行动者推进到下一位行动者。"
        return commands

    def _command_agent_action_allowed(self, session: GameSession, sender_id: str) -> bool:
        if sender_id not in session.players:
            return False
        return not is_turn_order_active(session) or is_current_turn(session, sender_id)

    def _validate_command_agent_line(
        self,
        session: GameSession,
        sender_id: str,
        command_line: str,
    ) -> str:
        command_token, rest = event_utils.split_first(
            str(command_line or "").strip()
        )
        command_name = (
            command_token[1:].lower()
            if command_token.startswith("/")
            else command_token.lower()
        )
        if not command_token.startswith("/trpg_"):
            return f"当前阶段不允许执行该 TRPG 命令：{command_token or command_line}"
        allowed_names = {
            event_utils.split_first(command)[0][1:].lower()
            for command in self._command_agent_allowed_commands(session, sender_id)
        }
        if command_name not in allowed_names:
            return f"当前阶段不允许执行该 TRPG 命令：/{command_name}"
        requires_args = {
            "trpg_act",
            "trpg_join",
            "trpg_memory",
            "trpg_roll",
            "trpg_preset",
        }
        if command_name in requires_args and not rest:
            return f"TRPG 命令缺少必要参数：/{command_name}"
        if command_name == "trpg_turn" and rest.lower() not in {"done", "next"}:
            return "TRPG 命令参数不合法：/trpg_turn"
        return ""

    async def _dispatch_trpg_message_command(
        self,
        event: AstrMessageEvent,
        raw_message: str,
    ):
        command_token, rest = event_utils.split_first(raw_message)
        command_name = (
            command_token[1:].lower()
            if command_token.startswith("/")
            else command_token.lower()
        )
        command_handlers = {
            "trpg_help": lambda: self.trpg_help(event),
            "trpg_start": lambda: self.trpg_start(event, rest),
            "trpg_join": lambda: self.trpg_join(event, rest),
            "trpg_preset": lambda: self.trpg_preset(event, rest),
            "trpg_pc": lambda: self.trpg_pc(event),
            "trpg_status": lambda: self.trpg_status(event),
            "trpg_turn": lambda: self.trpg_turn(event, rest),
            "trpg_recap": lambda: self.trpg_recap(event),
            "trpg_memory": lambda: self.trpg_memory(event, rest),
            "trpg_clues": lambda: self.trpg_clues(event),
            "trpg_act": lambda: self.trpg_act(event, rest),
            "trpg_roll": lambda: self.trpg_roll(event, rest),
            "trpg_end": lambda: self.trpg_end(event),
            "trpg_export": lambda: self.trpg_export(event),
        }
        handler_factory = command_handlers.get(command_name)
        if handler_factory is None:
            yield event.plain_result(f"未知 TRPG 命令：{command_token}")
            return
        async for item in handler_factory():
            yield item

    async def _preset_create(
        self,
        event: AstrMessageEvent,
        language: str,
        raw: str,
    ) -> str:
        name, concept = event_utils.split_first(str(raw or "").strip())
        if not name or not concept:
            return presentation.message(language, "preset_usage")
        user_id = event_utils.sender_id(event)
        presets = await self.storage.load_presets(user_id)
        if name in presets:
            return presentation.message(language, "preset_exists", name=name)
        presets[name] = CharacterPreset(
            name=name,
            character_name=name,
            concept=concept,
        )
        await self.storage.save_presets(user_id, presets)
        return presentation.message(language, "preset_created", name=name)

    async def _preset_list(self, event: AstrMessageEvent, language: str) -> str:
        presets = await self.storage.load_presets(event_utils.sender_id(event))
        if not presets:
            return presentation.message(language, "preset_empty")
        items = "\n".join(
            f"- {name}: {preset.character_name}, HP {preset.hp}, "
            f"SAN {preset.san}, {preset.concept}"
            for name, preset in sorted(presets.items())
        )
        return f"{presentation.message(language, 'preset_list_title')}\n{items}"

    async def _preset_show(
        self,
        event: AstrMessageEvent,
        language: str,
        raw: str,
    ) -> str:
        name = str(raw or "").strip()
        if not name:
            return presentation.message(language, "preset_usage")
        presets = await self.storage.load_presets(event_utils.sender_id(event))
        preset = presets.get(name)
        if preset is None:
            return presentation.message(language, "preset_not_found", name=name)
        return preset_commands.format_preset(language, preset)

    async def _preset_update(
        self,
        event: AstrMessageEvent,
        language: str,
        raw: str,
    ) -> str:
        name, rest = event_utils.split_first(str(raw or "").strip())
        field, value = event_utils.split_first(rest)
        if not name or not field or not value:
            return presentation.message(language, "preset_usage")
        user_id = event_utils.sender_id(event)
        presets = await self.storage.load_presets(user_id)
        preset = presets.get(name)
        if preset is None:
            return presentation.message(language, "preset_not_found", name=name)
        change = preset_commands.apply_preset_update(preset, field, value)
        presets[name] = preset
        await self.storage.save_presets(user_id, presets)
        return presentation.message(language, "preset_updated", name=name, change=change)

    def _register_web_apis(self) -> None:
        register_api = getattr(self.context, "register_web_api", None)
        if not callable(register_api):
            return
        routes = [
            (f"/{PLUGIN_NAME}/dashboard", self.web_dashboard, ["GET"], "TRPG dashboard"),
            (
                f"/{PLUGIN_NAME}/settings/save",
                self.web_save_settings,
                ["POST"],
                "Save TRPG settings",
            ),
            (f"/{PLUGIN_NAME}/scripts", self.web_list_scripts, ["GET"], "List scripts"),
            (
                f"/{PLUGIN_NAME}/scripts/<script_id>",
                self.web_get_script,
                ["GET"],
                "Get script",
            ),
            (
                f"/{PLUGIN_NAME}/scripts/save",
                self.web_save_script,
                ["POST"],
                "Save script",
            ),
            (
                f"/{PLUGIN_NAME}/scripts/delete",
                self.web_delete_script,
                ["POST"],
                "Delete script",
            ),
            (
                f"/{PLUGIN_NAME}/scripts/import",
                self.web_import_scripts,
                ["POST"],
                "Import scripts",
            ),
            (
                f"/{PLUGIN_NAME}/scripts/export",
                self.web_export_scripts,
                ["GET"],
                "Export scripts",
            ),
        ]
        for route, handler, methods, desc in routes:
            register_api(route, handler, methods, desc)

    async def web_dashboard(self):
        scripts = await self.storage.load_scenario_scripts()
        session_loader = getattr(self.storage, "load_saved_sessions", None)
        sessions = await session_loader() if callable(session_loader) else []
        return json_response(
            {
                "settings_schema": scenario_io.load_config_schema(),
                "settings": dict(self.config),
                "scripts": scenario_io.script_list_payload(scripts),
                "knowledge_entries": scenario_io.knowledge_entries_payload(sessions),
            }
        )

    async def web_save_settings(self):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("settings payload must be an object", status_code=400)
        try:
            updates = scenario_io.coerce_config_updates(
                scenario_io.load_config_schema(),
                payload,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        self.config.update(updates)
        saver = getattr(self.config, "save_config", None)
        if callable(saver):
            saver()
        return json_response({"settings": dict(self.config)})

    async def web_list_scripts(self):
        scripts = await self.storage.load_scenario_scripts()
        return json_response({"scripts": scenario_io.script_list_payload(scripts)})

    async def web_get_script(self, script_id: str):
        scripts = await self.storage.load_scenario_scripts()
        script = scripts.get(str(script_id))
        if script is None:
            return error_response("script not found", status_code=404)
        return json_response({"script": script.to_dict()})

    async def web_save_script(self):
        payload = await request.json(default={})
        if isinstance(payload, dict) and isinstance(payload.get("script"), dict):
            payload = payload["script"]
        if not isinstance(payload, dict):
            return error_response("script payload must be an object", status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        previous_created_at = payload.get("created_at")
        script = ScenarioScript.from_dict(payload)
        existing = scripts.get(script.script_id)
        if existing and not previous_created_at:
            script.created_at = existing.created_at
        script.updated_at = scenario_io.current_timestamp()
        scripts[script.script_id] = script
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"script": script.to_dict()})

    async def web_delete_script(self):
        payload = await request.json(default={})
        script_id = str(payload.get("script_id") or "").strip() if isinstance(payload, dict) else ""
        if not script_id:
            return error_response("script_id is required", status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        if script_id not in scripts:
            return error_response("script not found", status_code=404)
        del scripts[script_id]
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"deleted": script_id})

    async def web_import_scripts(self):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("import payload must be an object", status_code=400)
        content = str(payload.get("content") or "")
        filename = str(payload.get("filename") or "")
        if not content.strip():
            return error_response("content is required", status_code=400)
        try:
            imported = scenario_io.parse_scenario_import(content, filename=filename)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        for script in imported:
            existing = scripts.get(script.script_id)
            if existing:
                script.created_at = existing.created_at
            script.updated_at = scenario_io.current_timestamp()
            scripts[script.script_id] = script
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"scripts": [script.to_dict() for script in imported]})

    async def web_export_scripts(self):
        scripts = await self.storage.load_scenario_scripts()
        exports_dir = self.data_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        path = exports_dir / "scenario_scripts.json"
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(
                [script.to_dict() for script in scripts.values()],
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")
        return file_response(
            path,
            filename="scenario_scripts.json",
            content_type="application/json",
        )

    def _gm_system_prompt(self, session: GameSession | None = None) -> str:
        if session is not None and not self._session_feature_enabled(
            session,
            "structured_patch_enabled",
        ):
            return SIMPLE_GM_SYSTEM_PROMPT
        return str(self.config.get("gm_system_prompt") or DEFAULT_GM_SYSTEM_PROMPT)

    def _execute_dice_requests(
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

    def _apply_scene_and_memory(
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

    def _finish_turn(
        self,
        session: GameSession,
        event: AstrMessageEvent,
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

    async def _trim_recent_events(
        self,
        session: GameSession,
        event: AstrMessageEvent,
    ) -> None:
        limit = max(
            1, event_utils.safe_int(self.config.get("max_recent_events"), 20)
        )
        timeline_limit = event_utils.safe_int(
            self.config.get("max_timeline_events"), 80
        )
        if not self._session_feature_enabled(session, "knowledge_enabled"):
            session.recent_events = session.recent_events[-limit:]
            return
        if len(session.recent_events) <= limit:
            compact_campaign_knowledge(session, max_timeline=timeline_limit)
            return
        try:
            summary = await call_gm(
                self.context,
                event,
                prompt=build_summary_prompt(session),
                system_prompt=self._gm_system_prompt(session),
            )
            if summary:
                session.history_summary = summary
        except Exception:
            logger.warning("TRPG history summary update failed")
        session.recent_events = session.recent_events[-limit:]
        compact_campaign_knowledge(session, max_timeline=timeline_limit)

    def _turn_order_warning(self, session: GameSession, user_id: str) -> str:
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
