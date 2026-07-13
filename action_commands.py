from __future__ import annotations

from typing import Any, Awaitable, Callable

try:
    from . import event_utils, presentation
    from .astrbot_compat import Image, MessageChain, logger
    from .dice import roll_dice
    from .dice_gif import generate_dice_roll_gif
    from .gm import parse_structured_patch
    from .memory import apply_knowledge_patches, record_turn_timeline_event
    from .models import GameSession
    from .prompts import build_action_prompt, build_command_agent_prompt, build_resolution_prompt
    from .state import apply_state_patches
    from .turn_order import apply_turn_controls, advance_turn_order, can_submit_action, is_current_turn, is_turn_order_active
except ImportError:  # pragma: no cover - direct module loading outside package.
    import event_utils
    import presentation
    from astrbot_compat import Image, MessageChain, logger
    from dice import roll_dice
    from dice_gif import generate_dice_roll_gif
    from gm import parse_structured_patch
    from memory import apply_knowledge_patches, record_turn_timeline_event
    from models import GameSession
    from prompts import build_action_prompt, build_command_agent_prompt, build_resolution_prompt
    from state import apply_state_patches
    from turn_order import apply_turn_controls, advance_turn_order, can_submit_action, is_current_turn, is_turn_order_active


COMMAND_AGENT_SYSTEM_PROMPT = (
    "你是 TRPG 命令转换 Agent。只输出 JSON object，字段只能包含 command_line。"
)


class ActionCommandService:
    def __init__(
        self,
        owner: Any,
        *,
        call_gm: Callable[..., Awaitable[str]],
        call_command_agent: Callable[..., Awaitable[str]],
    ) -> None:
        self.owner = owner
        self.call_gm = call_gm
        self.call_command_agent = call_command_agent

    @property
    def storage(self):
        return self.owner.storage

    async def intercept(self, event: Any):
        session = await self.owner.runtime.running_session(event)
        if not session:
            return
        raw_message = event_utils.event_message_text(event)
        stripped = raw_message.strip()
        if stripped.startswith("/") and not stripped.lower().startswith("/trpg_"):
            return
        sender_id = event_utils.sender_id(event)
        is_direct_trpg_command = stripped.lower().startswith("/trpg_")
        command_agent_enabled = self.owner.runtime.session_feature_enabled(
            session, "command_agent_enabled"
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
                async for item in self.dispatch(event, stripped):
                    yield item
                return
            if not command_agent_enabled:
                async for item in self.owner.trpg_act(event, stripped):
                    yield item
                return

            try:
                command_line = await self.command_agent_command_line(
                    event, session, stripped
                )
            except ValueError:
                logger.warning("TRPG command agent returned invalid JSON")
                yield event.plain_result("命令转换 Agent 返回无效 JSON。")
                return
            if not command_line:
                if not self.command_agent_action_allowed(session, sender_id):
                    yield event.plain_result("当前阶段不允许提交角色行动。")
                    return
                command_line = f"/trpg_act {stripped}"

            error = self.validate_command_agent_line(
                session, sender_id, command_line
            )
            if error:
                yield event.plain_result(error)
                return
            async for item in self.dispatch(event, command_line):
                yield item
        except Exception:
            logger.exception("TRPG intercepted message handling failed")
            yield event.plain_result("跑团输入处理失败。")
        finally:
            event_utils.stop_event(event)

    async def act(self, event: Any, action: str = ""):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if event_utils.sender_id(event) not in session.players:
                yield event.plain_result(
                    presentation.message(session.language, "member_required")
                )
                return
            raw_action = str(action or "").strip()
            if not raw_action:
                yield event.plain_result(
                    presentation.message(session.language, "act_usage")
                )
                return
            if session.turn_count >= event_utils.safe_int(
                self.owner.config.get("max_turns"), 200
            ):
                yield event.plain_result(
                    presentation.message(session.language, "max_turns")
                )
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
            turn_warning = self.owner.runtime.turn_order_warning(session, sender_id)
            should_advance_turn = (
                session.turn_order.mode == "soft"
                and is_turn_order_active(session)
                and is_current_turn(session, sender_id)
            )
            raw_reply = await self.call_gm(
                self.owner.context,
                event,
                prompt=build_action_prompt(session, actor, raw_action),
                system_prompt=self.owner.runtime.gm_system_prompt(session),
            )

            if not self.owner.runtime.session_feature_enabled(
                session, "structured_patch_enabled"
            ):
                final = presentation.prepend_turn_warning(
                    turn_warning, raw_reply.strip()
                )
                self.owner.runtime.finish_turn(session, event, raw_action, final)
                await self.owner.runtime.trim_recent_events(
                    session, event, self.call_gm
                )
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            try:
                parsed = parse_structured_patch(
                    raw_reply,
                    strict=bool(self.owner.config.get("strict_json_patch", True)),
                )
            except Exception:
                logger.warning("TRPG GM JSON parse failed")
                final = "\n\n".join(
                    part
                    for part in (
                        raw_reply.strip(),
                        presentation.message(session.language, "json_failed"),
                    )
                    if part
                )
                final = presentation.prepend_turn_warning(turn_warning, final)
                if self.owner.runtime.session_feature_enabled(
                    session, "knowledge_enabled"
                ):
                    record_turn_timeline_event(
                        session, actor=actor, action=raw_action, outcome=final
                    )
                self.owner.runtime.finish_turn(session, event, raw_action, final)
                if should_advance_turn:
                    advance_turn_order(session)
                await self.owner.runtime.trim_recent_events(
                    session, event, self.call_gm
                )
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            if self.owner.runtime.session_feature_enabled(
                session, "dice_requests_enabled"
            ):
                dice_lines, dice_state_patches = (
                    self.owner.runtime.execute_dice_requests(
                        session, parsed.patch["dice_requests"]
                    )
                )
            else:
                dice_lines, dice_state_patches = [], []
            state_patches = [*dice_state_patches, *parsed.patch["state_patches"]]
            state_results = (
                apply_state_patches(session, state_patches)
                if self.owner.runtime.session_feature_enabled(
                    session, "state_patch_enabled"
                )
                else []
            )
            if self.owner.runtime.session_feature_enabled(
                session, "knowledge_enabled"
            ):
                apply_knowledge_patches(session, parsed.patch["knowledge_patches"])
            turn_results = (
                apply_turn_controls(session, parsed.patch["turn_controls"])
                if self.owner.runtime.session_feature_enabled(
                    session, "turn_order_enabled"
                )
                else []
            )
            self.owner.runtime.apply_scene_and_memory(
                session,
                parsed.patch,
                include_memory=self.owner.runtime.session_feature_enabled(
                    session, "knowledge_enabled"
                ),
            )

            dice_summary = "\n".join(dice_lines)
            state_summary = "\n".join(result.message for result in state_results)
            turn_summary = "\n".join(result.message for result in turn_results)
            resolution = ""
            if self.owner.runtime.session_feature_enabled(
                session, "second_pass_resolution_enabled"
            ) and (dice_summary or state_summary):
                try:
                    resolution = await self.call_gm(
                        self.owner.context,
                        event,
                        prompt=build_resolution_prompt(
                            session,
                            parsed.narrative,
                            dice_summary,
                            state_summary,
                        ),
                        system_prompt=self.owner.runtime.gm_system_prompt(session),
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
            if self.owner.runtime.session_feature_enabled(
                session, "knowledge_enabled"
            ):
                record_turn_timeline_event(
                    session, actor=actor, action=raw_action, outcome=final
                )
            self.owner.runtime.finish_turn(session, event, raw_action, final)
            if should_advance_turn:
                advance_turn_order(session)
            await self.owner.runtime.trim_recent_events(
                session, event, self.call_gm
            )
            await self.storage.save_session(session)
            yield event.plain_result(final)
        except Exception:
            logger.exception("TRPG act failed")
            yield event.plain_result(presentation.message("zh", "gm_failed"))

    async def roll(self, event: Any, expression: str = ""):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            language = (
                session.language
                if session and session.status == "running"
                else "zh"
            )
            expr = str(expression or "").strip()
            try:
                result = roll_dice(expr)
            except Exception as exc:
                yield event.plain_result(
                    presentation.message(language, "roll_failed", error=str(exc))
                )
                return

            output = presentation.format_roll_text(language, result)
            try:
                gif_path = generate_dice_roll_gif(
                    result, self.owner.data_dir / "dice_gifs"
                )
                chain_result = getattr(event, "chain_result", None)
                if not callable(chain_result):
                    raise RuntimeError(
                        "current AstrBot event does not support chain_result"
                    )
                if session and session.status == "running":
                    session.add_log(
                        user=event_utils.sender_label(event),
                        command="trpg_roll",
                        input_text=expr,
                        output_summary=(
                            f"GIF {gif_path.name}; "
                            f"{event_utils.one_line(output, 160)}"
                        ),
                    )
                    await self.storage.save_session(session)
                yield chain_result(
                    MessageChain([Image.fromFileSystem(str(gif_path))])
                )
                return
            except Exception as exc:
                logger.warning(
                    "TRPG dice GIF generation failed, using text fallback: %s", exc
                )

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

    async def command_agent_command_line(
        self, event: Any, session: GameSession, user_text: str
    ) -> str:
        sender_id = event_utils.sender_id(event)
        prompt = build_command_agent_prompt(
            session,
            sender_id=sender_id,
            sender_name=event_utils.sender_name(event),
            user_text=user_text,
            allowed_commands=self.command_agent_allowed_commands(
                session, sender_id
            ),
        )
        return await self.call_command_agent(
            self.owner.context,
            event,
            prompt=prompt,
            system_prompt=COMMAND_AGENT_SYSTEM_PROMPT,
        )

    def command_agent_allowed_commands(
        self, session: GameSession, sender_id: str
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
        if self.command_agent_action_allowed(session, sender_id):
            commands["/trpg_act <行动内容>"] = "提交当前角色行动。"
        if is_turn_order_active(session) and is_current_turn(session, sender_id):
            commands["/trpg_turn done"] = "当前行动者结束自己的行动并推进顺序。"
            commands["/trpg_turn next"] = "当前行动者推进到下一位行动者。"
        return commands

    @staticmethod
    def command_agent_action_allowed(session: GameSession, sender_id: str) -> bool:
        if sender_id not in session.players:
            return False
        return not is_turn_order_active(session) or is_current_turn(
            session, sender_id
        )

    def validate_command_agent_line(
        self, session: GameSession, sender_id: str, command_line: str
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
            for command in self.command_agent_allowed_commands(session, sender_id)
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

    async def dispatch(self, event: Any, raw_message: str):
        command_token, rest = event_utils.split_first(raw_message)
        command_name = (
            command_token[1:].lower()
            if command_token.startswith("/")
            else command_token.lower()
        )
        command_handlers = {
            "trpg_help": lambda: self.owner.trpg_help(event),
            "trpg_start": lambda: self.owner.trpg_start(event, rest),
            "trpg_join": lambda: self.owner.trpg_join(event, rest),
            "trpg_preset": lambda: self.owner.trpg_preset(event, rest),
            "trpg_pc": lambda: self.owner.trpg_pc(event),
            "trpg_status": lambda: self.owner.trpg_status(event),
            "trpg_turn": lambda: self.owner.trpg_turn(event, rest),
            "trpg_recap": lambda: self.owner.trpg_recap(event),
            "trpg_memory": lambda: self.owner.trpg_memory(event, rest),
            "trpg_clues": lambda: self.owner.trpg_clues(event),
            "trpg_act": lambda: self.owner.trpg_act(event, rest),
            "trpg_roll": lambda: self.owner.trpg_roll(event, rest),
            "trpg_end": lambda: self.owner.trpg_end(event),
            "trpg_export": lambda: self.owner.trpg_export(event),
        }
        handler_factory = command_handlers.get(command_name)
        if handler_factory is None:
            yield event.plain_result(f"未知 TRPG 命令：{command_token}")
            return
        async for item in handler_factory():
            yield item
