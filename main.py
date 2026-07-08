from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    from astrbot.api import AstrBotConfig, logger
    from astrbot.api.event import AstrMessageEvent, MessageChain, filter
    from astrbot.api.message_components import Image
    from astrbot.api.star import Context, Star, StarTools, register
    from astrbot.core.star.filter.command import GreedyStr
except ModuleNotFoundError:  # pragma: no cover - local syntax checks outside AstrBot.
    logger = logging.getLogger(__name__)
    AstrBotConfig = dict
    AstrMessageEvent = Any
    Context = Any
    GreedyStr = str

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

    class _Filter:
        @staticmethod
        def command(*_args: Any, **_kwargs: Any):
            def decorator(func: Any) -> Any:
                return func

            return decorator

    filter = _Filter()

    def register(*_args: Any, **_kwargs: Any):
        def decorator(cls: Any) -> Any:
            return cls

        return decorator

try:
    from .dice import roll_d20_check, roll_dice
    from .dice_gif import generate_dice_roll_gif
    from .export import export_session_markdown
    from .gm import call_gm, parse_structured_patch
    from .language import detect_language_from_theme
    from .models import (
        DEFAULT_ATTRIBUTES,
        CharacterPreset,
        GameSession,
        PlayerCharacter,
    )
    from .prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        build_action_prompt,
        build_opening_prompt,
        build_resolution_prompt,
        build_summary_prompt,
    )
    from .state import apply_state_patches
    from .storage import SessionStorage
except ImportError:  # pragma: no cover - direct module loading outside package.
    from dice import roll_d20_check, roll_dice
    from dice_gif import generate_dice_roll_gif
    from export import export_session_markdown
    from gm import call_gm, parse_structured_patch
    from language import detect_language_from_theme
    from models import (
        DEFAULT_ATTRIBUTES,
        CharacterPreset,
        GameSession,
        PlayerCharacter,
    )
    from prompts import (
        DEFAULT_GM_SYSTEM_PROMPT,
        build_action_prompt,
        build_opening_prompt,
        build_resolution_prompt,
        build_summary_prompt,
    )
    from state import apply_state_patches
    from storage import SessionStorage


PLUGIN_NAME = "astrbot_plugin_trpg_master"
PLUGIN_VERSION = "0.1.0"
PLUGIN_REPOSITORY = "https://github.com/penguin-madagascar/astrbot_plugin_trpg_master"
PLUGIN_DESCRIPTION = "LLM 驱动的 TRPG/跑团插件，Python 负责骰子、规则判定、状态和日志。"


MESSAGES = {
    "zh": {
        "no_session": "当前会话没有进行中的跑团，请先使用 /trpg_start [主题]。",
        "started_fallback": "跑团已启动，但 GM 开场生成失败。你们站在未知冒险的入口，危险正在靠近。",
        "join_usage": "用法：/trpg_join 角色名 一句话设定",
        "joined": "角色已加入：{name}（HP {hp} / SAN {san}）",
        "not_joined": "你还没有加入当前跑团，请先使用 /trpg_join 角色名 一句话设定。",
        "pc_title": "角色卡",
        "preset_title": "角色预设",
        "status_title": "跑团状态",
        "act_usage": "用法：/trpg_act 行动内容",
        "json_failed": "本回合未应用状态变更：GM 返回的 JSON 无法解析。",
        "roll_failed": "骰子表达式错误：{error}",
        "ended": "跑团已结束，日志已保留。",
        "exported": "跑团日志已导出：{path}",
        "max_turns": "当前跑团已达到最大回合数，请先 /trpg_end 或 /trpg_export。",
        "gm_failed": "GM 生成失败，请稍后重试。",
        "roll_title": "掷骰结果",
        "dice_title": "判定结果",
        "state_title": "状态变更",
        "success": "成功",
        "failure": "失败",
    },
    "en": {
        "no_session": "No running TRPG session here. Use /trpg_start [theme] first.",
        "started_fallback": "The session started, but the GM opening failed. You stand at the edge of an unknown adventure as danger draws near.",
        "join_usage": "Usage: /trpg_join character_name one-line concept",
        "joined": "Character joined: {name} (HP {hp} / SAN {san})",
        "not_joined": "You have not joined this session. Use /trpg_join character_name one-line concept first.",
        "pc_title": "Character Sheet",
        "preset_title": "Character Preset",
        "status_title": "Session Status",
        "act_usage": "Usage: /trpg_act action",
        "json_failed": "No state changes were applied this turn: the GM JSON could not be parsed.",
        "roll_failed": "Invalid dice expression: {error}",
        "ended": "Session ended. Logs were kept.",
        "exported": "Session log exported: {path}",
        "max_turns": "This session reached the configured turn limit. Use /trpg_end or /trpg_export.",
        "gm_failed": "GM generation failed. Please try again later.",
        "roll_title": "Dice Result",
        "dice_title": "Check Results",
        "state_title": "State Changes",
        "success": "success",
        "failure": "failure",
    },
    "ja": {
        "no_session": "現在進行中のセッションはありません。先に /trpg_start [テーマ] を使ってください。",
        "started_fallback": "セッションは開始しましたが、GM の導入生成に失敗しました。未知の冒険の入口で、危険が近づいています。",
        "join_usage": "使い方：/trpg_join キャラクター名 一言設定",
        "joined": "キャラクターが参加しました：{name}（HP {hp} / SAN {san}）",
        "not_joined": "まだこのセッションに参加していません。先に /trpg_join を使ってください。",
        "pc_title": "キャラクターシート",
        "preset_title": "キャラクタープリセット",
        "status_title": "セッション状況",
        "act_usage": "使い方：/trpg_act 行動内容",
        "json_failed": "GM の JSON を解析できなかったため、このターンの状態変更は適用されませんでした。",
        "roll_failed": "ダイス式エラー：{error}",
        "ended": "セッションを終了しました。ログは保存されています。",
        "exported": "セッションログを書き出しました：{path}",
        "max_turns": "このセッションは最大ターン数に達しました。/trpg_end または /trpg_export を使ってください。",
        "gm_failed": "GM 生成に失敗しました。後でもう一度試してください。",
        "roll_title": "ダイス結果",
        "dice_title": "判定結果",
        "state_title": "状態変更",
        "success": "成功",
        "failure": "失敗",
    },
    "ko": {
        "no_session": "현재 진행 중인 세션이 없습니다. 먼저 /trpg_start [테마] 를 사용하세요.",
        "started_fallback": "세션은 시작했지만 GM 도입 생성에 실패했습니다. 알 수 없는 모험의 입구에서 위험이 다가옵니다.",
        "join_usage": "사용법: /trpg_join 캐릭터명 한 줄 설정",
        "joined": "캐릭터가 참가했습니다: {name} (HP {hp} / SAN {san})",
        "not_joined": "아직 이 세션에 참가하지 않았습니다. 먼저 /trpg_join 을 사용하세요.",
        "pc_title": "캐릭터 시트",
        "preset_title": "캐릭터 프리셋",
        "status_title": "세션 상태",
        "act_usage": "사용법: /trpg_act 행동 내용",
        "json_failed": "GM JSON을 해석할 수 없어 이번 턴의 상태 변경은 적용되지 않았습니다.",
        "roll_failed": "주사위 식 오류: {error}",
        "ended": "세션을 종료했습니다. 로그는 보존됩니다.",
        "exported": "세션 로그를 내보냈습니다: {path}",
        "max_turns": "이 세션은 최대 턴 수에 도달했습니다. /trpg_end 또는 /trpg_export 를 사용하세요.",
        "gm_failed": "GM 생성에 실패했습니다. 잠시 후 다시 시도하세요.",
        "roll_title": "주사위 결과",
        "dice_title": "판정 결과",
        "state_title": "상태 변경",
        "success": "성공",
        "failure": "실패",
    },
}


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
        self.storage = SessionStorage(context, self.data_dir)

    @filter.command("trpg_help", desc="显示 LLM TRPG 插件帮助。")
    async def trpg_help(self, event: AstrMessageEvent):
        try:
            session = await self.storage.load_session(_session_id(event))
            language = session.language if session and session.status == "running" else "zh"
            yield event.plain_result(self._help_text(language))
        except Exception:
            logger.exception("TRPG help failed")
            yield event.plain_result("TRPG 帮助生成失败。")

    @filter.command("trpg_start", desc="启动新的 LLM TRPG 跑团。")
    async def trpg_start(self, event: AstrMessageEvent, theme: GreedyStr = ""):
        raw_theme = str(theme or "").strip()
        default_theme = str(self.config.get("default_theme") or "奇幻冒险")
        session_theme = raw_theme or default_theme
        language = detect_language_from_theme(raw_theme) if raw_theme else "zh"
        session = GameSession.new(
            session_id=_session_id(event),
            title=session_theme,
            theme=session_theme,
            language=language,
        )

        try:
            opening = await call_gm(
                self.context,
                event,
                prompt=build_opening_prompt(session),
                system_prompt=self._gm_system_prompt(),
            )
        except Exception:
            logger.exception("TRPG opening generation failed")
            opening = _msg(language, "started_fallback")

        session.scene["description"] = _one_line(opening, 500)
        session.recent_events.append(f"Session started: {session_theme}")
        session.add_log(
            user=_sender_label(event),
            command="trpg_start",
            input_text=session_theme,
            output_summary=_one_line(opening, 160),
        )
        await self.storage.save_session(session)
        yield event.plain_result(opening)

    @filter.command("trpg_join", desc="加入当前跑团并创建角色。")
    async def trpg_join(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            raw = str(query or "").strip()
            if not raw:
                yield event.plain_result(_msg(session.language, "join_usage"))
                return
            character_name, concept = _split_first(raw)
            if not character_name:
                yield event.plain_result(_msg(session.language, "join_usage"))
                return

            user_id = _sender_id(event)
            pc = PlayerCharacter(
                user_id=user_id,
                display_name=_sender_name(event),
                character_name=character_name,
                concept=concept,
            )
            session.players[user_id] = pc
            output = _msg(
                session.language,
                "joined",
                name=pc.character_name,
                hp=pc.hp,
                san=pc.san,
            )
            session.add_log(
                user=_sender_label(event),
                command="trpg_join",
                input_text=raw,
                output_summary=output,
            )
            await self.storage.save_session(session)
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG join failed")
            yield event.plain_result("加入跑团失败，请稍后重试。")

    @filter.command("trpg_pc", desc="查看自己的角色卡。")
    async def trpg_pc(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            pc = session.players.get(_sender_id(event))
            if not pc:
                yield event.plain_result(_msg(session.language, "not_joined"))
                return
            yield event.plain_result(self._format_pc(session.language, pc))
        except Exception:
            logger.exception("TRPG pc failed")
            yield event.plain_result("角色卡读取失败，请稍后重试。")

    @filter.command("trpg_status", desc="查看当前跑团状态。")
    async def trpg_status(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            yield event.plain_result(self._format_status(session))
        except Exception:
            logger.exception("TRPG status failed")
            yield event.plain_result("跑团状态读取失败，请稍后重试。")

    @filter.command("trpg_act", desc="提交玩家行动并推进剧情。")
    async def trpg_act(self, event: AstrMessageEvent, action: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            raw_action = str(action or "").strip()
            if not raw_action:
                yield event.plain_result(_msg(session.language, "act_usage"))
                return
            if session.turn_count >= _safe_int(self.config.get("max_turns"), 200):
                yield event.plain_result(_msg(session.language, "max_turns"))
                return

            actor = _sender_name(event)
            raw_reply = await call_gm(
                self.context,
                event,
                prompt=build_action_prompt(session, actor, raw_action),
                system_prompt=self._gm_system_prompt(),
            )

            try:
                parsed = parse_structured_patch(
                    raw_reply,
                    strict=bool(self.config.get("strict_json_patch", True)),
                )
            except Exception:
                logger.warning("TRPG GM JSON parse failed")
                final = "\n\n".join(
                    part for part in (raw_reply.strip(), _msg(session.language, "json_failed")) if part
                )
                self._finish_turn(session, event, raw_action, final)
                await self._trim_recent_events(session, event)
                await self.storage.save_session(session)
                yield event.plain_result(final)
                return

            dice_lines = self._execute_dice_requests(
                session,
                parsed.patch["dice_requests"],
            )
            state_results = (
                apply_state_patches(session, parsed.patch["state_patches"])
                if bool(self.config.get("allow_state_patch", True))
                else []
            )
            self._apply_scene_and_memory(session, parsed.patch)

            dice_summary = "\n".join(dice_lines)
            state_summary = "\n".join(result.message for result in state_results)
            resolution = ""
            if bool(self.config.get("second_pass_resolution", True)) and (
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
                        system_prompt=self._gm_system_prompt(),
                    )
                except Exception:
                    logger.warning("TRPG second pass resolution failed")

            final = self._compose_action_output(
                session.language,
                parsed.narrative,
                dice_summary,
                state_summary,
                resolution,
            )
            self._finish_turn(session, event, raw_action, final)
            await self._trim_recent_events(session, event)
            await self.storage.save_session(session)
            yield event.plain_result(final)
        except Exception:
            logger.exception("TRPG act failed")
            yield event.plain_result(_msg("zh", "gm_failed"))

    @filter.command("trpg_roll", desc="掷基础骰子表达式。")
    async def trpg_roll(self, event: AstrMessageEvent, expression: GreedyStr = ""):
        try:
            session = await self.storage.load_session(_session_id(event))
            language = session.language if session and session.status == "running" else "zh"
            expr = str(expression or "").strip()
            try:
                result = roll_dice(expr)
            except Exception as exc:
                yield event.plain_result(_msg(language, "roll_failed", error=str(exc)))
                return

            output = _format_roll_text(language, result)
            try:
                gif_path = generate_dice_roll_gif(result, self.data_dir / "dice_gifs")
                chain_result = getattr(event, "chain_result", None)
                if not callable(chain_result):
                    raise RuntimeError("current AstrBot event does not support chain_result")
                if session and session.status == "running":
                    session.add_log(
                        user=_sender_label(event),
                        command="trpg_roll",
                        input_text=expr,
                        output_summary=f"GIF {gif_path.name}; {_one_line(output, 160)}",
                    )
                    await self.storage.save_session(session)
                yield chain_result(MessageChain([Image.fromFileSystem(str(gif_path))]))
                return
            except Exception as exc:
                logger.warning("TRPG dice GIF generation failed, using text fallback: %s", exc)

            if session and session.status == "running":
                session.add_log(
                    user=_sender_label(event),
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
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            session.status = "ended"
            output = _msg(session.language, "ended")
            session.add_log(
                user=_sender_label(event),
                command="trpg_end",
                input_text="",
                output_summary=output,
            )
            await self.storage.save_session(session)
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG end failed")
            yield event.plain_result("结束跑团失败，请稍后重试。")

    @filter.command("trpg_export", desc="导出当前跑团 Markdown 日志。")
    async def trpg_export(self, event: AstrMessageEvent):
        try:
            session = await self.storage.load_session(_session_id(event))
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            path = export_session_markdown(session, self.data_dir)
            output = _msg(session.language, "exported", path=str(path))
            yield event.plain_result(output)
        except Exception:
            logger.exception("TRPG export failed")
            yield event.plain_result("导出跑团日志失败，请稍后重试。")

    async def _running_session(self, event: AstrMessageEvent) -> GameSession | None:
        session = await self.storage.load_session(_session_id(event))
        if not session or session.status != "running":
            return None
        if not session.language:
            session.language = str(self.config.get("response_language") or "zh")
        return session

    def _gm_system_prompt(self) -> str:
        return str(self.config.get("gm_system_prompt") or DEFAULT_GM_SYSTEM_PROMPT)

    def _execute_dice_requests(
        self,
        session: GameSession,
        requests: list[dict[str, Any]],
    ) -> list[str]:
        lines: list[str] = []
        for index, request in enumerate(requests, start=1):
            actor_name = str(request.get("actor") or "")
            skill = str(request.get("skill") or "DEX").upper()
            reason = str(request.get("reason") or "")
            try:
                dc = int(request.get("dc", 10))
            except (TypeError, ValueError):
                dc = 10
            pc = session.player_by_character_name(actor_name)
            attr_value = pc.attributes.get(skill, 10) if pc else 10
            result = roll_d20_check(attr_value, dc)
            outcome = _msg(
                session.language,
                "success" if result.success else "failure",
            )
            natural = f", {result.natural}" if result.natural else ""
            actor_label = actor_name or f"#{index}"
            lines.append(
                f"{actor_label} {skill} vs DC {dc}: "
                f"d20={result.roll}, mod={result.attribute_modifier}, "
                f"total={result.total} => {outcome}{natural}"
                + (f" ({reason})" if reason else "")
            )
        return lines

    def _apply_scene_and_memory(
        self,
        session: GameSession,
        patch: dict[str, Any],
    ) -> None:
        scene_patch = patch.get("scene_patch") or {}
        if isinstance(scene_patch, dict):
            for key in ("location", "description"):
                value = scene_patch.get(key)
                if value:
                    session.scene[key] = str(value)
        session.plot_threads.extend(
            item for item in patch.get("new_plot_threads", []) if item
        )
        session.recent_events.extend(
            item for item in patch.get("memory_notes", []) if item
        )

    def _compose_action_output(
        self,
        language: str,
        narrative: str,
        dice_summary: str,
        state_summary: str,
        resolution: str,
    ) -> str:
        parts = [narrative.strip()]
        if dice_summary:
            parts.append(f"{_msg(language, 'dice_title')}\n{dice_summary}")
        if state_summary:
            parts.append(f"{_msg(language, 'state_title')}\n{state_summary}")
        if resolution:
            parts.append(resolution.strip())
        return "\n\n".join(part for part in parts if part)

    def _finish_turn(
        self,
        session: GameSession,
        event: AstrMessageEvent,
        action: str,
        output: str,
    ) -> None:
        session.turn_count += 1
        summary = f"{_sender_name(event)}: {action} -> {_one_line(output, 180)}"
        session.recent_events.append(summary)
        session.add_log(
            user=_sender_label(event),
            command="trpg_act",
            input_text=action,
            output_summary=_one_line(output, 200),
        )

    async def _trim_recent_events(
        self,
        session: GameSession,
        event: AstrMessageEvent,
    ) -> None:
        limit = max(1, _safe_int(self.config.get("max_recent_events"), 20))
        if len(session.recent_events) <= limit:
            return
        try:
            summary = await call_gm(
                self.context,
                event,
                prompt=build_summary_prompt(session),
                system_prompt=self._gm_system_prompt(),
            )
            if summary:
                session.history_summary = summary
        except Exception:
            logger.warning("TRPG history summary update failed")
        session.recent_events = session.recent_events[-limit:]

    def _format_pc(self, language: str, pc: PlayerCharacter) -> str:
        attrs = ", ".join(f"{key} {value}" for key, value in pc.attributes.items())
        inventory = ", ".join(pc.inventory) if pc.inventory else "-"
        status = ", ".join(pc.status_effects) if pc.status_effects else "-"
        return (
            f"{_msg(language, 'pc_title')}: {pc.character_name}\n"
            f"Player: {pc.display_name}\n"
            f"Concept: {pc.concept}\n"
            f"HP: {pc.hp} / SAN: {pc.san}\n"
            f"Attributes: {attrs}\n"
            f"Inventory: {inventory}\n"
            f"Status: {status}"
        )

    def _format_status(self, session: GameSession) -> str:
        players = "\n".join(
            f"- {pc.character_name}: HP {pc.hp}, SAN {pc.san}, {pc.concept}"
            for pc in session.players.values()
        ) or "- none"
        npcs = "\n".join(
            f"- {npc.name}: {npc.role} {npc.status}".strip()
            for npc in session.npcs.values()
        ) or "- none"
        threads = "\n".join(f"- {item}" for item in session.plot_threads) or "- none"
        scene = session.scene.get("description") or session.scene.get("location") or "-"
        return (
            f"{_msg(session.language, 'status_title')}: {session.title}\n"
            f"Language: {session.language}\n"
            f"Turn: {session.turn_count}\n"
            f"Scene: {scene}\n"
            f"Players:\n{players}\n"
            f"NPCs:\n{npcs}\n"
            f"Plot Threads:\n{threads}\n"
            f"Summary: {session.history_summary or '-'}"
        )

    def _help_text(self, language: str) -> str:
        if language == "en":
            return (
                "LLM TRPG commands:\n"
                "/trpg_start [theme] - start a session\n"
                "/trpg_join <name> <concept> - join as a PC\n"
                "/trpg_pc - show your character sheet\n"
                "/trpg_status - show session state\n"
                "/trpg_act <action> - take an action\n"
                "/trpg_roll <expr> - roll dice as a GIF, e.g. 1d20+3\n"
                "/trpg_end - end the session\n"
                "/trpg_export - export Markdown log"
            )
        return (
            "LLM TRPG 指令：\n"
            "/trpg_start [主题] - 启动跑团\n"
            "/trpg_join <角色名> <一句话设定> - 加入并创建角色\n"
            "/trpg_pc - 查看自己的角色卡\n"
            "/trpg_status - 查看当前跑团状态\n"
            "/trpg_act <行动内容> - 执行行动并推进剧情\n"
            "/trpg_roll <表达式> - 生成 GIF 掷骰，例如 1d20+3\n"
            "/trpg_end - 结束当前跑团\n"
            "/trpg_export - 导出 Markdown 日志"
        )


def _msg(language: str, key: str, **kwargs: Any) -> str:
    table = MESSAGES.get(language, MESSAGES["zh"])
    template = table.get(key, MESSAGES["zh"][key])
    return template.format(**kwargs)


def _format_roll_text(language: str, result: Any) -> str:
    return (
        f"{_msg(language, 'roll_title')}: {result.expression}\n"
        f"rolls={result.rolls}, modifier={result.modifier}, total={result.total}"
    )


def _format_preset(language: str, preset: CharacterPreset) -> str:
    attrs = ", ".join(f"{key} {value}" for key, value in preset.attributes.items())
    skills = ", ".join(f"{key} {value}" for key, value in preset.skills.items()) or "-"
    inventory = ", ".join(preset.inventory) if preset.inventory else "-"
    status = ", ".join(preset.status_effects) if preset.status_effects else "-"
    return (
        f"{_msg(language, 'preset_title')}: {preset.name}\n"
        f"Character: {preset.character_name}\n"
        f"Concept: {preset.concept}\n"
        f"HP: {preset.hp} / SAN: {preset.san}\n"
        f"Attributes: {attrs}\n"
        f"Skills: {skills}\n"
        f"Inventory: {inventory}\n"
        f"Status: {status}"
    )


def _apply_preset_update(
    preset: CharacterPreset,
    field_name: str,
    raw_value: str,
) -> str:
    field = str(field_name or "").strip()
    value = str(raw_value or "").strip()
    field_lower = field.lower()
    field_upper = field.upper()
    if not field:
        raise ValueError("属性名称不能为空。")

    if field_lower in {"name", "character_name"}:
        if not value:
            raise ValueError("角色名不能为空。")
        preset.character_name = value
        return f"character_name={value}"
    if field_lower == "concept":
        if not value:
            raise ValueError("设定不能为空。")
        preset.concept = value
        return f"concept={value}"
    if field_lower == "hp":
        preset.hp = _parse_update_int(value, "hp")
        return f"hp={preset.hp}"
    if field_lower == "san":
        preset.san = _parse_update_int(value, "san")
        return f"san={preset.san}"
    if field_upper in DEFAULT_ATTRIBUTES:
        preset.attributes[field_upper] = _parse_update_int(value, field_upper)
        return f"{field_upper}={preset.attributes[field_upper]}"
    if field_lower.startswith("attr."):
        attr_name = field[5:].strip().upper()
        if not attr_name:
            raise ValueError("属性名称不能为空。")
        preset.attributes[attr_name] = _parse_update_int(value, attr_name)
        return f"{attr_name}={preset.attributes[attr_name]}"
    if field_lower.startswith("skill."):
        skill_name = field[6:].strip()
        if not skill_name:
            raise ValueError("技能名称不能为空。")
        preset.skills[skill_name] = _parse_update_int(value, skill_name)
        return f"{skill_name}={preset.skills[skill_name]}"
    if field_lower == "inventory":
        preset.inventory = _split_preset_list_value(value)
        return f"inventory={', '.join(preset.inventory) or '-'}"
    if field_lower in {"status", "status_effects"}:
        preset.status_effects = _split_preset_list_value(value)
        return f"status={', '.join(preset.status_effects) or '-'}"

    raise ValueError(f"不支持的属性名称：{field}")


def _parse_update_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是整数。") from exc


def _split_preset_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if text == "-":
        return []
    for separator in ("，", "、"):
        text = text.replace(separator, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _session_id(event: Any) -> str:
    return str(
        getattr(event, "unified_msg_origin", "")
        or getattr(event, "session_id", "")
        or "default"
    )


def _sender_id(event: Any) -> str:
    getter = getattr(event, "get_sender_id", None)
    if callable(getter):
        value = getter()
    else:
        value = getattr(event, "sender_id", "")
    return str(value or "unknown")


def _sender_name(event: Any) -> str:
    getter = getattr(event, "get_sender_name", None)
    if callable(getter):
        value = getter()
    else:
        value = getattr(event, "sender_name", "")
    return str(value or _sender_id(event))


def _sender_label(event: Any) -> str:
    return f"{_sender_name(event)}({_sender_id(event)})"


def _split_first(value: str) -> tuple[str, str]:
    parts = value.split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _one_line(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit]


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
