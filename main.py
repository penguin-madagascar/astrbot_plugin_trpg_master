from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

try:
    from astrbot.api import AstrBotConfig, logger
    from astrbot.api.event import AstrMessageEvent, MessageChain, filter
    from astrbot.api.message_components import Image
    from astrbot.api.star import Context, Star, StarTools, register
    from astrbot.api.web import error_response, file_response, json_response, request
    from astrbot.core.star.filter.command import GreedyStr
except ModuleNotFoundError:  # pragma: no cover - local syntax checks outside AstrBot.
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

try:
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
        DEFAULT_ATTRIBUTES,
        CharacterPreset,
        GameSession,
        PlayerCharacter,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
        normalize_ruleset_id,
        normalize_turn_order_mode,
        utc_now_iso,
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
    from .rules import get_ruleset, resolve_check_request
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
        DEFAULT_ATTRIBUTES,
        CharacterPreset,
        GameSession,
        PlayerCharacter,
        ScenarioScript,
        default_feature_flags,
        normalize_feature_flags,
        normalize_play_mode,
        normalize_ruleset_id,
        normalize_turn_order_mode,
        utc_now_iso,
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
    from rules import get_ruleset, resolve_check_request
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


MESSAGES = {
    "zh": {
        "no_session": "当前会话没有进行中的跑团，请先使用 /trpg_start [主题]。",
        "started_fallback": "跑团已启动，但 GM 开场生成失败。你们站在未知冒险的入口，危险正在靠近。",
        "join_usage": "用法：/trpg_join 角色名 一句话设定",
        "joined": "角色已加入：{name}（HP {hp} / SAN {san}）",
        "not_joined": "你还没有加入当前跑团，请先使用 /trpg_join 角色名 一句话设定。",
        "pc_title": "角色卡",
        "preset_title": "角色预设",
        "preset_usage": "用法：/trpg_preset create 名称 一句话设定 | list | show 名称 | update 名称 属性名称 新值",
        "preset_created": "角色预设已创建：{name}",
        "preset_exists": "角色预设已存在：{name}",
        "preset_not_found": "未找到你的角色预设：{name}",
        "preset_empty": "你还没有角色预设。",
        "preset_list_title": "你的角色预设：",
        "preset_updated": "角色预设已更新：{name}（{change}）",
        "preset_ruleset_mismatch": "角色预设规则不匹配：{name} 是 {preset_ruleset}，当前跑团是 {session_ruleset}。",
        "status_title": "跑团状态",
        "act_usage": "用法：/trpg_act 行动内容",
        "turn_usage": "用法：/trpg_turn [done|next]",
        "turn_disabled": "当前跑团未启用行动顺序。",
        "turn_title": "行动顺序",
        "turn_none": "暂无建议行动者",
        "turn_advanced": "行动顺序已推进。当前建议行动者：{current}",
        "turn_denied_done": "只有当前行动者可以推进行动顺序。",
        "turn_denied_action": "当前不是你的行动回合。当前建议行动者：{current}",
        "turn_out_of_order": "行动顺序提示：当前建议行动者是 {current}。",
        "turn_control_title": "行动顺序",
        "memory_usage": "用法：/trpg_memory 关键词",
        "memory_empty": "没有找到可见的战役记忆。",
        "memory_title": "战役记忆",
        "clues_empty": "当前没有可见线索。",
        "clues_title": "可见线索",
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
        "preset_usage": "Usage: /trpg_preset create name concept | list | show name | update name field value",
        "preset_created": "Character preset created: {name}",
        "preset_exists": "Character preset already exists: {name}",
        "preset_not_found": "Character preset not found: {name}",
        "preset_empty": "You do not have any character presets.",
        "preset_list_title": "Your character presets:",
        "preset_updated": "Character preset updated: {name} ({change})",
        "preset_ruleset_mismatch": "Character preset ruleset mismatch: {name} is {preset_ruleset}, current session is {session_ruleset}.",
        "status_title": "Session Status",
        "act_usage": "Usage: /trpg_act action",
        "turn_usage": "Usage: /trpg_turn [done|next]",
        "turn_disabled": "Turn order is not enabled for this session.",
        "turn_title": "Turn Order",
        "turn_none": "No suggested actor",
        "turn_advanced": "Turn order advanced. Current suggested actor: {current}",
        "turn_denied_done": "Only the current actor can advance turn order.",
        "turn_denied_action": "It is not your turn. Current suggested actor: {current}",
        "turn_out_of_order": "Turn order note: the current suggested actor is {current}.",
        "turn_control_title": "Turn Order",
        "memory_usage": "Usage: /trpg_memory keyword",
        "memory_empty": "No visible campaign memory found.",
        "memory_title": "Campaign Memory",
        "clues_empty": "No visible clues yet.",
        "clues_title": "Visible Clues",
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
        self._register_web_apis()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def trpg_message_intercept(self, event: AstrMessageEvent):
        session = await self._running_session(event)
        if not session:
            return

        raw_message = _event_message_text(event)
        stripped = raw_message.strip()
        if stripped.startswith("/") and not stripped.lower().startswith("/trpg_"):
            return
        sender_id = _sender_id(event)
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

        _block_default_llm(event)
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
            _stop_event(event)

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
        requested_mode, script_query = _split_start_mode(raw_theme)
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
            session_id=_session_id(event),
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
            session.history_summary = _scenario_history_summary(script)
            session.scene["description"] = script.opening_scene
            session.plot_threads.extend(script.hooks)
            if feature_flags.get("knowledge_enabled", True):
                _initialize_scenario_knowledge(session, script)

        try:
            opening = await call_gm(
                self.context,
                event,
                prompt=build_opening_prompt(session),
                system_prompt=self._gm_system_prompt(session),
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
            if raw.lower().startswith("preset:"):
                preset_name = raw[len("preset:") :].strip()
                if not preset_name:
                    yield event.plain_result(_msg(session.language, "join_usage"))
                    return
                user_id = _sender_id(event)
                presets = await self.storage.load_presets(user_id)
                preset = presets.get(preset_name)
                if preset is None:
                    yield event.plain_result(
                        _msg(session.language, "preset_not_found", name=preset_name)
                    )
                    return
                if preset.ruleset_id != session.ruleset_id:
                    yield event.plain_result(
                        _msg(
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
                    display_name=_sender_name(event),
                )
                session.players[user_id] = pc
                add_player_to_turn_order(session, user_id)
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
                ruleset_id=session.ruleset_id,
            )
            session.players[user_id] = pc
            add_player_to_turn_order(session, user_id)
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

    @filter.command("trpg_preset", desc="管理自己的 TRPG 角色预设。")
    async def trpg_preset(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            language = await self._command_language(event)
            raw = str(query or "").strip()
            action, rest = _split_first(raw)
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
            yield event.plain_result(_msg(language, "preset_usage"))
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

    @filter.command("trpg_turn", desc="查看或管理当前跑团行动顺序。")
    async def trpg_turn(self, event: AstrMessageEvent, query: GreedyStr = ""):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
                return
            if not session.turn_order.enabled:
                yield event.plain_result(_msg(session.language, "turn_disabled"))
                return

            raw = str(query or "").strip()
            action = _split_first(raw)[0].lower()
            sender_id = _sender_id(event)

            if not action:
                yield event.plain_result(self._format_turn_order(session))
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
                    yield event.plain_result(_msg(session.language, "turn_denied_done"))
                    return
                advance_turn_order(session)
                await self.storage.save_session(session)
                yield event.plain_result(self._turn_advanced_message(session))
                return

            yield event.plain_result(_msg(session.language, "turn_usage"))
        except Exception:
            logger.exception("TRPG turn command failed")
            yield event.plain_result("行动顺序操作失败，请稍后重试。")

    @filter.command("trpg_recap", desc="查看玩家可见的战役回顾。")
    async def trpg_recap(self, event: AstrMessageEvent):
        try:
            session = await self._running_session(event)
            if not session:
                yield event.plain_result(_msg("zh", "no_session"))
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
                yield event.plain_result(_msg("zh", "no_session"))
                return
            keyword = str(query or "").strip()
            if not keyword:
                yield event.plain_result(_msg(session.language, "memory_usage"))
                return
            results = search_campaign_memory(
                session,
                query=keyword,
                visibility="player",
            )
            if not results:
                yield event.plain_result(_msg(session.language, "memory_empty"))
                return
            output = f"{_msg(session.language, 'memory_title')}:\n" + "\n".join(
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
                yield event.plain_result(_msg("zh", "no_session"))
                return
            clues = player_visible_clues(session)
            if not clues:
                yield event.plain_result(_msg(session.language, "clues_empty"))
                return
            output = f"{_msg(session.language, 'clues_title')}:\n" + "\n".join(
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
                yield event.plain_result(_msg("zh", "no_session"))
                return
            raw_action = str(action or "").strip()
            if not raw_action:
                yield event.plain_result(_msg(session.language, "act_usage"))
                return
            if session.turn_count >= _safe_int(self.config.get("max_turns"), 200):
                yield event.plain_result(_msg(session.language, "max_turns"))
                return

            sender_id = _sender_id(event)
            actor_pc = session.players.get(sender_id)
            actor = actor_pc.character_name if actor_pc else _sender_name(event)
            if not can_submit_action(session, sender_id):
                yield event.plain_result(
                    _msg(
                        session.language,
                        "turn_denied_action",
                        current=self._turn_current_label(session),
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
                final = self._prepend_turn_warning(turn_warning, raw_reply.strip())
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
                    part for part in (raw_reply.strip(), _msg(session.language, "json_failed")) if part
                )
                final = self._prepend_turn_warning(turn_warning, final)
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

            final = self._compose_action_output(
                session.language,
                parsed.narrative,
                dice_summary,
                state_summary,
                turn_summary,
                resolution,
            )
            final = self._prepend_turn_warning(turn_warning, final)
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
        session = await self.storage.load_session(_session_id(event))
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
            flags["command_agent_enabled"] = _config_bool(
                self.config,
                "command_agent_enabled",
                True,
            )
            flags["turn_order_enabled"] = (
                True if script else _config_bool(self.config, "turn_order_enabled", True)
            )
            flags["state_patch_enabled"] = _config_bool(
                self.config,
                "allow_state_patch",
                True,
            )
            flags["second_pass_resolution_enabled"] = _config_bool(
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
            return enabled and _config_bool(self.config, "command_agent_enabled", True)
        if key == "state_patch_enabled":
            return enabled and _config_bool(self.config, "allow_state_patch", True)
        if key == "second_pass_resolution_enabled":
            return enabled and _config_bool(self.config, "second_pass_resolution", True)
        return enabled

    async def _command_agent_command_line(
        self,
        event: AstrMessageEvent,
        session: GameSession,
        user_text: str,
    ) -> str:
        sender_id = _sender_id(event)
        prompt = build_command_agent_prompt(
            session,
            sender_id=sender_id,
            sender_name=_sender_name(event),
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
        command_token, rest = _split_first(str(command_line or "").strip())
        command_name = (
            command_token[1:].lower()
            if command_token.startswith("/")
            else command_token.lower()
        )
        if not command_token.startswith("/trpg_"):
            return f"当前阶段不允许执行该 TRPG 命令：{command_token or command_line}"
        allowed_names = {
            _split_first(command)[0][1:].lower()
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
        command_token, rest = _split_first(raw_message)
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
        name, concept = _split_first(str(raw or "").strip())
        if not name or not concept:
            return _msg(language, "preset_usage")
        user_id = _sender_id(event)
        presets = await self.storage.load_presets(user_id)
        if name in presets:
            return _msg(language, "preset_exists", name=name)
        presets[name] = CharacterPreset(
            name=name,
            character_name=name,
            concept=concept,
        )
        await self.storage.save_presets(user_id, presets)
        return _msg(language, "preset_created", name=name)

    async def _preset_list(self, event: AstrMessageEvent, language: str) -> str:
        presets = await self.storage.load_presets(_sender_id(event))
        if not presets:
            return _msg(language, "preset_empty")
        items = "\n".join(
            f"- {name}: {preset.character_name}, HP {preset.hp}, "
            f"SAN {preset.san}, {preset.concept}"
            for name, preset in sorted(presets.items())
        )
        return f"{_msg(language, 'preset_list_title')}\n{items}"

    async def _preset_show(
        self,
        event: AstrMessageEvent,
        language: str,
        raw: str,
    ) -> str:
        name = str(raw or "").strip()
        if not name:
            return _msg(language, "preset_usage")
        presets = await self.storage.load_presets(_sender_id(event))
        preset = presets.get(name)
        if preset is None:
            return _msg(language, "preset_not_found", name=name)
        return _format_preset(language, preset)

    async def _preset_update(
        self,
        event: AstrMessageEvent,
        language: str,
        raw: str,
    ) -> str:
        name, rest = _split_first(str(raw or "").strip())
        field, value = _split_first(rest)
        if not name or not field or not value:
            return _msg(language, "preset_usage")
        user_id = _sender_id(event)
        presets = await self.storage.load_presets(user_id)
        preset = presets.get(name)
        if preset is None:
            return _msg(language, "preset_not_found", name=name)
        change = _apply_preset_update(preset, field, value)
        presets[name] = preset
        await self.storage.save_presets(user_id, presets)
        return _msg(language, "preset_updated", name=name, change=change)

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
                "settings_schema": _load_config_schema(),
                "settings": dict(self.config),
                "scripts": _script_list_payload(scripts),
                "knowledge_entries": _knowledge_entries_payload(sessions),
            }
        )

    async def web_save_settings(self):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("settings payload must be an object", status_code=400)
        updates = _coerce_config_updates(_load_config_schema(), payload)
        self.config.update(updates)
        saver = getattr(self.config, "save_config", None)
        if callable(saver):
            saver()
        return json_response({"settings": dict(self.config)})

    async def web_list_scripts(self):
        scripts = await self.storage.load_scenario_scripts()
        return json_response({"scripts": _script_list_payload(scripts)})

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
        script.updated_at = _current_timestamp()
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
            imported = _parse_scenario_import(content, filename=filename)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        for script in imported:
            existing = scripts.get(script.script_id)
            if existing:
                script.created_at = existing.created_at
            script.updated_at = _current_timestamp()
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

    def _compose_action_output(
        self,
        language: str,
        narrative: str,
        dice_summary: str,
        state_summary: str,
        turn_summary: str,
        resolution: str,
    ) -> str:
        parts = [narrative.strip()]
        if dice_summary:
            parts.append(f"{_msg(language, 'dice_title')}\n{dice_summary}")
        if state_summary:
            parts.append(f"{_msg(language, 'state_title')}\n{state_summary}")
        if turn_summary:
            parts.append(f"{_msg(language, 'turn_control_title')}\n{turn_summary}")
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
        timeline_limit = _safe_int(self.config.get("max_timeline_events"), 80)
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

    def _turn_current_label(self, session: GameSession) -> str:
        player = current_turn_player(session)
        if player is None:
            return _msg(session.language, "turn_none")
        return player.character_name

    def _turn_advanced_message(self, session: GameSession) -> str:
        return _msg(
            session.language,
            "turn_advanced",
            current=self._turn_current_label(session),
        )

    def _turn_order_warning(self, session: GameSession, user_id: str) -> str:
        if session.turn_order.mode != "soft":
            return ""
        if not is_turn_order_active(session) or is_current_turn(session, user_id):
            return ""
        player = current_turn_player(session)
        if player is None:
            return ""
        return _msg(
            session.language,
            "turn_out_of_order",
            current=player.character_name,
        )

    @staticmethod
    def _prepend_turn_warning(warning: str, output: str) -> str:
        return "\n\n".join(part for part in (warning, output) if part)

    def _format_turn_order(self, session: GameSession) -> str:
        order = session.turn_order
        queue_lines = []
        for index, user_id in enumerate(order.queue):
            player = session.players.get(user_id)
            if player is None:
                continue
            marker = "->" if index == order.current_index else "  "
            queue_lines.append(f"{marker} {player.character_name} ({player.display_name})")
        queue = "\n".join(queue_lines) or "- none"
        paused = "yes" if order.paused else "no"
        return (
            f"{_msg(session.language, 'turn_title')}: {session.title}\n"
            f"Mode: {order.mode}\n"
            f"Phase: {order.phase}\n"
            f"Round: {order.round_count}\n"
            f"Paused: {paused}\n"
            f"Current: {self._turn_current_label(session)}\n"
            f"Queue:\n{queue}\n"
            f"Control Note: {order.control_note or '-'}"
        )

    def _format_pc(self, language: str, pc: PlayerCharacter) -> str:
        card = get_ruleset(pc.ruleset_id).format_character(pc)
        return f"{_msg(language, 'pc_title')}: {pc.character_name}\n{card}"

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
        turn_order = (
            self._format_turn_order(session)
            if session.turn_order.enabled
            else _msg(session.language, "turn_disabled")
        )
        return (
            f"{_msg(session.language, 'status_title')}: {session.title}\n"
            f"Language: {session.language}\n"
            f"Ruleset: {session.ruleset_id}\n"
            f"Turn: {session.turn_count}\n"
            f"Scene: {scene}\n"
            f"Players:\n{players}\n"
            f"NPCs:\n{npcs}\n"
            f"Plot Threads:\n{threads}\n"
            f"Rule Nodes:\n{_format_session_rule_nodes(session)}\n"
            f"{turn_order}\n"
            f"Summary: {session.history_summary or '-'}"
        )

    def _help_text(self, language: str) -> str:
        if language == "en":
            return (
                "LLM TRPG commands:\n"
                "/trpg_start [simple|advanced] [theme] - start a session\n"
                "/trpg_join <name> <concept> - join as a PC\n"
                "/trpg_join preset:<name> - join with your preset\n"
                "/trpg_preset create <name> <concept> - create a preset\n"
                "/trpg_preset list|show|update ... - manage your presets\n"
                "/trpg_pc - show your character sheet\n"
                "/trpg_status - show session state\n"
                "/trpg_turn [done|next] - show or advance turn order\n"
                "/trpg_recap - show player-visible campaign recap\n"
                "/trpg_memory <keyword> - search campaign memory\n"
                "/trpg_clues - show visible clues\n"
                "/trpg_act <action> - take an action\n"
                "/trpg_roll <expr> - roll dice as a GIF, e.g. 1d20+3\n"
                "/trpg_end - end the session\n"
                "/trpg_export - export Markdown log"
            )
        return (
            "LLM TRPG 指令：\n"
            "/trpg_start [简易|进阶] [主题或剧本名] - 启动跑团\n"
            "/trpg_join <角色名> <一句话设定> - 加入并创建角色\n"
            "/trpg_join preset:<名称> - 使用自己的角色预设加入\n"
            "/trpg_preset create <名称> <一句话设定> - 创建角色预设\n"
            "/trpg_preset list - 列出自己的角色预设\n"
            "/trpg_preset show <名称> - 查看角色预设\n"
            "/trpg_preset update <名称> <属性名称> <新值> - 微调一个字段\n"
            "/trpg_pc - 查看自己的角色卡\n"
            "/trpg_status - 查看当前跑团状态\n"
            "/trpg_turn [done|next] - 查看或推进行动顺序\n"
            "/trpg_recap - 查看玩家可见战役回顾\n"
            "/trpg_memory <关键词> - 搜索玩家可见战役记忆\n"
            "/trpg_clues - 查看玩家可见线索\n"
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
    pc = preset.to_player_character(user_id="", display_name="")
    return f"{_msg(language, 'preset_title')}: {preset.name}\n" + get_ruleset(
        preset.ruleset_id
    ).format_character(pc)


def _format_session_rule_nodes(session: GameSession) -> str:
    scenario = session.scenario_script if isinstance(session.scenario_script, dict) else {}
    nodes = [item for item in scenario.get("rule_nodes", []) if isinstance(item, dict)]
    if not nodes:
        return "- none"
    return "\n".join(
        f"- {str(node.get('title') or node.get('node_id') or 'untitled')}"
        for node in nodes
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


def _scenario_history_summary(script: ScenarioScript) -> str:
    parts = [
        f"剧本简介：{script.summary}" if script.summary else "",
        f"剧本背景：{script.background}" if script.background else "",
        f"GM 备注：{script.gm_notes}" if script.gm_notes else "",
    ]
    return "\n".join(part for part in parts if part)


def _initialize_scenario_knowledge(
    session: GameSession,
    script: ScenarioScript,
) -> None:
    patches: list[dict[str, Any]] = []
    if script.summary:
        patches.append(
            {
                "op": "add_fact",
                "text": script.summary,
                "visibility": "public",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.background:
        patches.append(
            {
                "op": "add_fact",
                "text": script.background,
                "visibility": "gm_only",
                "importance": 4,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.gm_notes:
        patches.append(
            {
                "op": "add_fact",
                "text": script.gm_notes,
                "visibility": "gm_only",
                "importance": 5,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    if script.opening_scene:
        patches.append(
            {
                "op": "add_timeline_event",
                "summary": f"剧本开场：{script.opening_scene}",
                "visibility": "public",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    for index, hook in enumerate(script.hooks, start=1):
        patches.append(
            {
                "op": "update_clue",
                "clue_id": f"hook-{index}",
                "title": hook,
                "detail": hook,
                "clue_status": "available",
                "visibility": "private",
                "importance": 3,
                "tags": script.tags,
                "source": "scenario",
            }
        )
    apply_knowledge_patches(session, patches)


def _script_list_payload(scripts: dict[str, ScenarioScript]) -> list[dict[str, Any]]:
    return [
        script.to_dict()
        for script in sorted(scripts.values(), key=lambda item: item.title)
    ]


def _knowledge_entries_payload(sessions: list[GameSession]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for session in sessions:
        knowledge = session.campaign_knowledge
        base = {
            "session_id": session.session_id,
            "session_title": session.title,
        }
        entries.extend(
            {
                **base,
                "type": "timeline",
                "id": entry.event_id,
                "title": f"T{entry.turn}",
                "summary": entry.summary,
                "visibility": entry.visibility,
                "status": entry.status,
                "importance": entry.importance,
            }
            for entry in knowledge.timeline
        )
        entries.extend(
            {
                **base,
                "type": "entity",
                "id": entity.entity_id,
                "title": entity.name,
                "summary": entity.summary,
                "visibility": entity.visibility,
                "status": entity.status,
                "importance": entity.importance,
            }
            for entity in knowledge.entities.values()
        )
        entries.extend(
            {
                **base,
                "type": "fact",
                "id": fact.fact_id,
                "title": fact.text,
                "summary": fact.text,
                "visibility": fact.visibility,
                "status": fact.status,
                "importance": fact.importance,
            }
            for fact in knowledge.facts
        )
        entries.extend(
            {
                **base,
                "type": "clue",
                "id": clue.clue_id,
                "title": clue.title,
                "summary": clue.detail,
                "visibility": clue.visibility,
                "status": clue.status,
                "importance": clue.importance,
            }
            for clue in knowledge.clues.values()
        )
        entries.extend(
            {
                **base,
                "type": "thread",
                "id": thread.thread_id,
                "title": thread.title,
                "summary": thread.summary,
                "visibility": thread.visibility,
                "status": thread.status,
                "importance": thread.importance,
            }
            for thread in knowledge.threads.values()
        )
        entries.extend(
            {
                **base,
                "type": "relationship",
                "id": relationship.relationship_id,
                "title": f"{relationship.source} -> {relationship.target}",
                "summary": relationship.description,
                "visibility": relationship.visibility,
                "status": relationship.status,
                "importance": relationship.importance,
            }
            for relationship in knowledge.relationships
        )
    return entries


def _parse_scenario_import(content: str, filename: str = "") -> list[ScenarioScript]:
    text = str(content or "").strip()
    if not text:
        raise ValueError("导入内容不能为空。")
    if filename.lower().endswith(".json") or text[0] in "[{":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            if filename.lower().endswith(".json"):
                raise ValueError("JSON 剧本格式无法解析。") from exc
            return [_parse_markdown_scenario(text)]
        if isinstance(payload, dict) and isinstance(payload.get("scripts"), list):
            payload = payload["scripts"]
        if isinstance(payload, list):
            return [ScenarioScript.from_dict(item) for item in payload]
        if isinstance(payload, dict):
            return [ScenarioScript.from_dict(payload)]
        raise ValueError("JSON 剧本必须是对象、对象数组或包含 scripts 数组的对象。")
    return [_parse_markdown_scenario(text)]


def _parse_markdown_scenario(markdown: str) -> ScenarioScript:
    title = ""
    sections: dict[str, list[str]] = {}
    current = "gm_notes"
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            heading_text = heading.group(2).strip()
            if heading.group(1) == "#" and not title:
                title = heading_text
                continue
            current = _markdown_section_key(heading_text)
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    if not title:
        title = "导入剧本"
    hooks = _markdown_list_items("\n".join(sections.get("hooks", [])))
    tags = _split_preset_list_value(_section_text(sections, "tags"))
    gm_notes = _section_text(sections, "gm_notes")
    unknown = _section_text(sections, "unknown")
    if unknown:
        gm_notes = "\n\n".join(part for part in (gm_notes, unknown) if part)
    return ScenarioScript(
        script_id="",
        title=title,
        language=_section_text(sections, "language") or "zh",
        play_mode=_section_text(sections, "play_mode") or "advanced",
        theme=_section_text(sections, "theme") or title,
        summary=_section_text(sections, "summary"),
        background=_section_text(sections, "background"),
        opening_scene=_section_text(sections, "opening_scene"),
        hooks=hooks,
        gm_notes=gm_notes,
        tags=tags,
        turn_order_mode=_section_text(sections, "turn_order_mode") or "llm_gm",
        ruleset_id=_section_text(sections, "ruleset_id") or "d20_lite",
        rule_nodes=_parse_markdown_rule_nodes(_section_text(sections, "rule_nodes")),
        feature_flags=_parse_markdown_feature_flags(
            _section_text(sections, "feature_flags")
        ),
    )


def _markdown_section_key(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    mapping = {
        "简介": "summary",
        "summary": "summary",
        "背景": "background",
        "background": "background",
        "开场": "opening_scene",
        "开场场景": "opening_scene",
        "opening": "opening_scene",
        "opening scene": "opening_scene",
        "opening_scene": "opening_scene",
        "线索": "hooks",
        "钩子": "hooks",
        "hooks": "hooks",
        "主题": "theme",
        "theme": "theme",
        "语言": "language",
        "language": "language",
        "模式": "play_mode",
        "玩法模式": "play_mode",
        "play_mode": "play_mode",
        "play mode": "play_mode",
        "mode": "play_mode",
        "标签": "tags",
        "tags": "tags",
        "行动顺序": "turn_order_mode",
        "行动顺序模式": "turn_order_mode",
        "turn_order_mode": "turn_order_mode",
        "turn order": "turn_order_mode",
        "turn mode": "turn_order_mode",
        "规则": "ruleset_id",
        "规则系统": "ruleset_id",
        "ruleset": "ruleset_id",
        "ruleset_id": "ruleset_id",
        "rule set": "ruleset_id",
        "检定节点": "rule_nodes",
        "规则节点": "rule_nodes",
        "rule_nodes": "rule_nodes",
        "rule nodes": "rule_nodes",
        "checks": "rule_nodes",
        "机制开关": "feature_flags",
        "功能开关": "feature_flags",
        "feature_flags": "feature_flags",
        "feature flags": "feature_flags",
        "features": "feature_flags",
        "gm 备注": "gm_notes",
        "gm备注": "gm_notes",
        "gm notes": "gm_notes",
        "notes": "gm_notes",
        "备注": "gm_notes",
    }
    return mapping.get(normalized, "unknown")


def _section_text(sections: dict[str, list[str]], key: str) -> str:
    lines = sections.get(key, [])
    return "\n".join(line.strip() for line in lines).strip()


def _markdown_list_items(value: str) -> list[str]:
    items = []
    for line in value.splitlines():
        item = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
        if item:
            items.append(item)
    return items


def _parse_markdown_rule_nodes(value: str) -> list[dict[str, Any]]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _parse_markdown_feature_flags(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _coerce_config_updates(
    schema: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key, definition in schema.items():
        if key not in payload:
            continue
        field_type = str((definition or {}).get("type") or "string")
        value = payload[key]
        if field_type in {"string", "text"}:
            updates[key] = str(value)
        elif field_type == "int":
            updates[key] = int(value)
        elif field_type == "bool":
            updates[key] = _coerce_bool(value)
        else:
            updates[key] = value
    return updates


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value)


def _load_config_schema() -> dict[str, Any]:
    path = Path(__file__).with_name("_conf_schema.json")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def _current_timestamp() -> str:
    return utc_now_iso()


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


def _event_message_text(event: Any) -> str:
    getter = getattr(event, "get_message_str", None)
    if callable(getter):
        value = getter()
    else:
        value = getattr(event, "message_str", "")
    return str(value or "")


def _block_default_llm(event: Any) -> None:
    blocker = getattr(event, "should_call_llm", None)
    if callable(blocker):
        blocker(True)
        return
    setattr(event, "call_llm", True)


def _stop_event(event: Any) -> None:
    stopper = getattr(event, "stop_event", None)
    if callable(stopper):
        stopper()


def _split_first(value: str) -> tuple[str, str]:
    parts = value.split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _split_start_mode(value: str) -> tuple[str, str]:
    first, rest = _split_first(str(value or "").strip())
    mode = normalize_play_mode(first, default="")
    if mode:
        return mode, rest.strip()
    return "", str(value or "").strip()


def _one_line(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit]


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _config_bool(config: AstrBotConfig | dict, key: str, default: bool) -> bool:
    if key not in config:
        return default
    return _coerce_bool(config.get(key))
