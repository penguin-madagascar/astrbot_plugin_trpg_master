from __future__ import annotations

from typing import Any, Awaitable, Callable

try:
    from . import event_utils, preset_commands, presentation, scenario_io
    from .astrbot_compat import logger
    from .export import export_session_markdown
    from .language import detect_language_from_theme
    from .memory import format_campaign_recap, player_visible_clues, search_campaign_memory
    from .models import CharacterPreset, GameSession, PlayerCharacter, normalize_ruleset_id, normalize_turn_order_mode
    from .prompts import build_opening_prompt
    from .turn_order import add_player_to_turn_order, advance_turn_order, can_finish_turn, initialize_turn_order
except ImportError:  # pragma: no cover - direct module loading outside package.
    import event_utils
    import preset_commands
    import presentation
    import scenario_io
    from astrbot_compat import logger
    from export import export_session_markdown
    from language import detect_language_from_theme
    from memory import format_campaign_recap, player_visible_clues, search_campaign_memory
    from models import CharacterPreset, GameSession, PlayerCharacter, normalize_ruleset_id, normalize_turn_order_mode
    from prompts import build_opening_prompt
    from turn_order import add_player_to_turn_order, advance_turn_order, can_finish_turn, initialize_turn_order


class SessionCommandService:
    def __init__(
        self,
        owner: Any,
        *,
        call_gm: Callable[..., Awaitable[str]],
    ) -> None:
        self.owner = owner
        self.call_gm = call_gm

    @property
    def storage(self):
        return self.owner.storage

    async def help(self, event: Any):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            language = session.language if session and session.status == "running" else "zh"
            yield event.plain_result(presentation.help_text(language))
        except Exception:
            logger.exception("TRPG help failed")
            yield event.plain_result("TRPG 帮助生成失败。")

    async def start(self, event: Any, theme: str = ""):
        session_id = event_utils.session_id(event)
        existing = await self.storage.load_session(session_id)
        if existing and existing.status == "running":
            yield event.plain_result(
                presentation.message(existing.language, "session_running")
            )
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
        default_theme = str(self.owner.config.get("default_theme") or "奇幻冒险")
        script = (
            await self.storage.find_scenario_script(script_query)
            if script_query
            else None
        )
        play_mode = requested_mode or (script.play_mode if script else "simple")
        feature_flags = self.owner.runtime.start_feature_flags(play_mode, script)
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
            else normalize_ruleset_id(
                self.owner.config.get("default_ruleset_id") or "d20_lite"
            )
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
        turn_mode = (
            script.turn_order_mode
            if script
            else normalize_turn_order_mode(
                self.owner.config.get("turn_order_mode") or "llm_gm"
            )
        )
        initialize_turn_order(
            session,
            enabled=bool(feature_flags.get("turn_order_enabled", True)),
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
            opening = await self.call_gm(
                self.owner.context,
                event,
                prompt=build_opening_prompt(session),
                system_prompt=self.owner.runtime.gm_system_prompt(session),
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

    async def join(self, event: Any, query: str = ""):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            raw = str(query or "").strip()
            if not raw:
                yield event.plain_result(
                    presentation.message(session.language, "join_usage")
                )
                return
            if raw.lower().startswith("preset:"):
                preset_name = raw[len("preset:") :].strip()
                if not preset_name:
                    yield event.plain_result(
                        presentation.message(session.language, "join_usage")
                    )
                    return
                user_id = event_utils.sender_id(event)
                presets = await self.storage.load_presets(user_id)
                preset = presets.get(preset_name)
                if preset is None:
                    yield event.plain_result(
                        presentation.message(
                            session.language, "preset_not_found", name=preset_name
                        )
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
            else:
                character_name, concept = event_utils.split_first(raw)
                if not character_name:
                    yield event.plain_result(
                        presentation.message(session.language, "join_usage")
                    )
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

    async def preset(self, event: Any, query: str = ""):
        try:
            language = await self.owner.runtime.command_language(event)
            action, rest = event_utils.split_first(str(query or "").strip())
            handlers = {
                "create": self._preset_create,
                "list": self._preset_list,
                "show": self._preset_show,
                "update": self._preset_update,
            }
            handler = handlers.get(action.lower())
            if handler is None:
                yield event.plain_result(
                    presentation.message(language, "preset_usage")
                )
                return
            output = await handler(event, language, rest)
            yield event.plain_result(output)
        except ValueError as exc:
            yield event.plain_result(str(exc))
        except Exception:
            logger.exception("TRPG preset command failed")
            yield event.plain_result("角色预设操作失败，请稍后重试。")

    async def pc(self, event: Any):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            pc = session.players.get(event_utils.sender_id(event))
            if not pc:
                yield event.plain_result(
                    presentation.message(session.language, "not_joined")
                )
                return
            yield event.plain_result(presentation.format_pc(session.language, pc))
        except Exception:
            logger.exception("TRPG pc failed")
            yield event.plain_result("角色卡读取失败，请稍后重试。")

    async def status(self, event: Any):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            yield event.plain_result(presentation.format_status(session))
        except Exception:
            logger.exception("TRPG status failed")
            yield event.plain_result("跑团状态读取失败，请稍后重试。")

    async def turn(self, event: Any, query: str = ""):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if not session.turn_order.enabled:
                yield event.plain_result(
                    presentation.message(session.language, "turn_disabled")
                )
                return
            action = event_utils.split_first(str(query or "").strip())[0].lower()
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
                    async for item in self.owner.trpg_act(event, request_text):
                        yield item
                    return
                if not can_finish_turn(session, sender_id):
                    yield event.plain_result(
                        presentation.message(session.language, "turn_denied_done")
                    )
                    return
                advance_turn_order(session)
                await self.storage.save_session(session)
                yield event.plain_result(
                    presentation.turn_advanced_message(session)
                )
                return
            yield event.plain_result(
                presentation.message(session.language, "turn_usage")
            )
        except Exception:
            logger.exception("TRPG turn command failed")
            yield event.plain_result("行动顺序操作失败，请稍后重试。")

    async def recap(self, event: Any):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            yield event.plain_result(
                format_campaign_recap(session, visibility="player")
            )
        except Exception:
            logger.exception("TRPG recap command failed")
            yield event.plain_result("战役回顾读取失败，请稍后重试。")

    async def memory(self, event: Any, query: str = ""):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            keyword = str(query or "").strip()
            if not keyword:
                yield event.plain_result(
                    presentation.message(session.language, "memory_usage")
                )
                return
            results = search_campaign_memory(
                session, query=keyword, visibility="player"
            )
            if not results:
                yield event.plain_result(
                    presentation.message(session.language, "memory_empty")
                )
                return
            output = (
                f"{presentation.message(session.language, 'memory_title')}:\n"
                + "\n".join(f"- {item}" for item in results)
            )
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG memory command failed")
            yield event.plain_result("战役记忆搜索失败，请稍后重试。")

    async def clues(self, event: Any):
        try:
            session = await self.owner.runtime.running_session(event)
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            clues = player_visible_clues(session)
            if not clues:
                yield event.plain_result(
                    presentation.message(session.language, "clues_empty")
                )
                return
            output = (
                f"{presentation.message(session.language, 'clues_title')}:\n"
                + "\n".join(
                    f"- {clue.title} [{clue.clue_status}]: {clue.detail}"
                    for clue in clues
                )
            )
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG clues command failed")
            yield event.plain_result("线索读取失败，请稍后重试。")

    async def end(self, event: Any):
        session = None
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
            await self.storage.delete_session(session.session_id)
            yield event.plain_result(presentation.message(session.language, "ended"))
        except Exception:
            logger.exception("TRPG end failed")
            language = session.language if session else "zh"
            yield event.plain_result(presentation.message(language, "end_failed"))

    async def export(self, event: Any):
        try:
            session = await self.storage.load_session(event_utils.session_id(event))
            if not session:
                yield event.plain_result(presentation.message("zh", "no_session"))
                return
            if event_utils.sender_id(event) not in session.players:
                yield event.plain_result(
                    presentation.message(session.language, "member_required")
                )
                return
            path = export_session_markdown(session, self.owner.data_dir)
            yield event.plain_result(
                presentation.message(session.language, "exported", path=str(path))
            )
        except Exception:
            logger.exception("TRPG export failed")
            yield event.plain_result("导出跑团日志失败，请稍后重试。")

    async def _preset_create(self, event: Any, language: str, raw: str) -> str:
        name, concept = event_utils.split_first(str(raw or "").strip())
        if not name or not concept:
            return presentation.message(language, "preset_usage")
        user_id = event_utils.sender_id(event)
        presets = await self.storage.load_presets(user_id)
        if name in presets:
            return presentation.message(language, "preset_exists", name=name)
        presets[name] = CharacterPreset(
            name=name, character_name=name, concept=concept
        )
        await self.storage.save_presets(user_id, presets)
        return presentation.message(language, "preset_created", name=name)

    async def _preset_list(self, event: Any, language: str, _raw: str) -> str:
        presets = await self.storage.load_presets(event_utils.sender_id(event))
        if not presets:
            return presentation.message(language, "preset_empty")
        items = "\n".join(
            f"- {name}: {preset.character_name}, HP {preset.hp}, "
            f"SAN {preset.san}, {preset.concept}"
            for name, preset in sorted(presets.items())
        )
        return f"{presentation.message(language, 'preset_list_title')}\n{items}"

    async def _preset_show(self, event: Any, language: str, raw: str) -> str:
        name = str(raw or "").strip()
        if not name:
            return presentation.message(language, "preset_usage")
        presets = await self.storage.load_presets(event_utils.sender_id(event))
        preset = presets.get(name)
        if preset is None:
            return presentation.message(language, "preset_not_found", name=name)
        return preset_commands.format_preset(language, preset)

    async def _preset_update(self, event: Any, language: str, raw: str) -> str:
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
        return presentation.message(
            language, "preset_updated", name=name, change=change
        )
