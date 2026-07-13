from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .application import TRPGRuntime
    from .astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Image,
        MessageChain,
        Star,
        StarTools,
        filter,
        logger,
        register,
        request,
    )
except ImportError:  # pragma: no cover - direct module loading outside package.
    from application import TRPGRuntime
    from astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Image,
        MessageChain,
        Star,
        StarTools,
        filter,
        logger,
        register,
        request,
    )

try:
    from . import event_utils
    from . import presentation
    from .session_commands import SessionCommandService
    from . import web_dashboard
    from .dice import roll_dice
    from .dice_gif import generate_dice_roll_gif
    from .gm import call_command_agent, call_gm, parse_structured_patch
    from .memory import (
        apply_knowledge_patches,
        record_turn_timeline_event,
    )
    from .models import GameSession
    from .prompts import (
        build_action_prompt,
        build_command_agent_prompt,
        build_resolution_prompt,
    )
    from .state import apply_state_patches
    from .storage import SessionStorage
    from .turn_order import (
        apply_turn_controls,
        advance_turn_order,
        can_submit_action,
        is_current_turn,
        is_turn_order_active,
    )
except ImportError:  # pragma: no cover - direct module loading outside package.
    import event_utils
    import presentation
    from session_commands import SessionCommandService
    import web_dashboard
    from dice import roll_dice
    from dice_gif import generate_dice_roll_gif
    from gm import call_command_agent, call_gm, parse_structured_patch
    from memory import (
        apply_knowledge_patches,
        record_turn_timeline_event,
    )
    from models import GameSession
    from prompts import (
        build_action_prompt,
        build_command_agent_prompt,
        build_resolution_prompt,
    )
    from state import apply_state_patches
    from storage import SessionStorage
    from turn_order import (
        apply_turn_controls,
        advance_turn_order,
        can_submit_action,
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
        self.runtime = TRPGRuntime(self)
        web_dashboard.register_web_apis(self.context, PLUGIN_NAME, self)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def trpg_message_intercept(self, event: AstrMessageEvent):
        session = await self.runtime.running_session(event)
        if not session:
            return

        raw_message = event_utils.event_message_text(event)
        stripped = raw_message.strip()
        if stripped.startswith("/") and not stripped.lower().startswith("/trpg_"):
            return
        sender_id = event_utils.sender_id(event)
        is_direct_trpg_command = stripped.lower().startswith("/trpg_")
        command_agent_enabled = self.runtime.session_feature_enabled(
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
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.help(event):
            yield item

    @filter.command("trpg_start", desc="启动新的 LLM TRPG 跑团。")
    async def trpg_start(self, event: AstrMessageEvent, theme: GreedyStr = ""):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.start(event, theme):
            yield item

    @filter.command("trpg_join", desc="加入当前跑团并创建角色。")
    async def trpg_join(self, event: AstrMessageEvent, query: GreedyStr = ""):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.join(event, query):
            yield item

    @filter.command("trpg_preset", desc="管理自己的 TRPG 角色预设。")
    async def trpg_preset(self, event: AstrMessageEvent, query: GreedyStr = ""):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.preset(event, query):
            yield item

    @filter.command("trpg_pc", desc="查看自己的角色卡。")
    async def trpg_pc(self, event: AstrMessageEvent):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.pc(event):
            yield item

    @filter.command("trpg_status", desc="查看当前跑团状态。")
    async def trpg_status(self, event: AstrMessageEvent):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.status(event):
            yield item

    @filter.command("trpg_turn", desc="查看或管理当前跑团行动顺序。")
    async def trpg_turn(self, event: AstrMessageEvent, query: GreedyStr = ""):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.turn(event, query):
            yield item

    @filter.command("trpg_recap", desc="查看玩家可见的战役回顾。")
    async def trpg_recap(self, event: AstrMessageEvent):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.recap(event):
            yield item

    @filter.command("trpg_memory", desc="搜索玩家可见的战役记忆。")
    async def trpg_memory(self, event: AstrMessageEvent, query: GreedyStr = ""):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.memory(event, query):
            yield item

    @filter.command("trpg_clues", desc="查看玩家可见线索。")
    async def trpg_clues(self, event: AstrMessageEvent):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.clues(event):
            yield item

    @filter.command("trpg_act", desc="提交玩家行动并推进剧情。")
    async def trpg_act(self, event: AstrMessageEvent, action: GreedyStr = ""):
        try:
            session = await self.runtime.running_session(event)
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
            turn_warning = self.runtime.turn_order_warning(session, sender_id)
            should_advance_turn = (
                session.turn_order.mode == "soft"
                and is_turn_order_active(session)
                and is_current_turn(session, sender_id)
            )
            raw_reply = await call_gm(
                self.context,
                event,
                prompt=build_action_prompt(session, actor, raw_action),
                system_prompt=self.runtime.gm_system_prompt(session),
            )

            if not self.runtime.session_feature_enabled(
                session, "structured_patch_enabled"
            ):
                final = presentation.prepend_turn_warning(turn_warning, raw_reply.strip())
                self.runtime.finish_turn(session, event, raw_action, final)
                await self.runtime.trim_recent_events(
                    session, event, call_gm
                )
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
                if self.runtime.session_feature_enabled(session, "knowledge_enabled"):
                    record_turn_timeline_event(
                        session,
                        actor=actor,
                        action=raw_action,
                        outcome=final,
                    )
                self.runtime.finish_turn(session, event, raw_action, final)
                if should_advance_turn:
                    advance_turn_order(session)
                await self.runtime.trim_recent_events(session, event, call_gm)
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            if self.runtime.session_feature_enabled(session, "dice_requests_enabled"):
                dice_lines, dice_state_patches = self.runtime.execute_dice_requests(
                    session,
                    parsed.patch["dice_requests"],
                )
            else:
                dice_lines, dice_state_patches = [], []
            state_patches = [*dice_state_patches, *parsed.patch["state_patches"]]
            state_results = (
                apply_state_patches(session, state_patches)
                if self.runtime.session_feature_enabled(session, "state_patch_enabled")
                else []
            )
            if self.runtime.session_feature_enabled(session, "knowledge_enabled"):
                apply_knowledge_patches(session, parsed.patch["knowledge_patches"])
            turn_results = (
                apply_turn_controls(session, parsed.patch["turn_controls"])
                if self.runtime.session_feature_enabled(session, "turn_order_enabled")
                else []
            )
            self.runtime.apply_scene_and_memory(
                session,
                parsed.patch,
                include_memory=self.runtime.session_feature_enabled(
                    session, "knowledge_enabled"
                ),
            )

            dice_summary = "\n".join(dice_lines)
            state_summary = "\n".join(result.message for result in state_results)
            turn_summary = "\n".join(result.message for result in turn_results)
            resolution = ""
            if self.runtime.session_feature_enabled(
                session, "second_pass_resolution_enabled"
            ) and (
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
                        system_prompt=self.runtime.gm_system_prompt(session),
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
            if self.runtime.session_feature_enabled(session, "knowledge_enabled"):
                record_turn_timeline_event(
                    session,
                    actor=actor,
                    action=raw_action,
                    outcome=final,
                )
            self.runtime.finish_turn(session, event, raw_action, final)
            if should_advance_turn:
                advance_turn_order(session)
            await self.runtime.trim_recent_events(session, event, call_gm)
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
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.end(event):
            yield item

    @filter.command("trpg_export", desc="导出当前跑团 Markdown 日志。")
    async def trpg_export(self, event: AstrMessageEvent):
        service = SessionCommandService(self, call_gm=call_gm)
        async for item in service.export(event):
            yield item

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


    async def web_dashboard(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).dashboard()

    async def web_save_settings(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).save_settings(request)

    async def web_list_scripts(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).list_scripts()

    async def web_get_script(self, script_id: str):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).get_script(script_id)

    async def web_save_script(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).save_script(request)

    async def web_delete_script(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).delete_script(request)

    async def web_import_scripts(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).import_scripts(request)

    async def web_export_scripts(self):
        return await web_dashboard.WebDashboardService(
            self.storage, self.config, self.data_dir
        ).export_scripts()
