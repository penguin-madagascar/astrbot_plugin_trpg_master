from __future__ import annotations

from typing import Any

try:
    from .models import GameSession, PlayerCharacter
    from .rules import get_ruleset
    from .turn_order import current_turn_player
except ImportError:  # pragma: no cover - direct module loading outside package.
    from models import GameSession, PlayerCharacter
    from rules import get_ruleset
    from turn_order import current_turn_player


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
        "ended": "跑团已结束，当前会话数据已删除。",
        "end_failed": "结束跑团失败，当前会话数据未删除。",
        "exported": "跑团日志已导出：{path}",
        "session_running": "当前会话已有进行中的跑团，请先使用 /trpg_end；如需保留记录，请先 /trpg_export。",
        "start_cleanup_failed": "无法清理旧跑团数据，新跑团未启动。",
        "member_required": "只有已加入当前跑团的玩家可以执行此操作。",
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
        "ended": "Session ended. The current session data was deleted.",
        "end_failed": "The session could not be ended, and its data was not deleted.",
        "exported": "Session log exported: {path}",
        "session_running": "A TRPG session is already running here. Use /trpg_end first, and /trpg_export first if you need to keep a record.",
        "start_cleanup_failed": "The previous session data could not be removed, so the new session was not started.",
        "member_required": "Only players who joined this TRPG session may perform this operation.",
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
        "ended": "セッションを終了し、現在のセッションデータを削除しました。",
        "end_failed": "セッションを終了できず、データは削除されませんでした。",
        "exported": "セッションログを書き出しました：{path}",
        "session_running": "この会話ではすでにセッションが進行中です。先に /trpg_end を使用し、記録を残す場合はその前に /trpg_export を使用してください。",
        "start_cleanup_failed": "以前のセッションデータを削除できなかったため、新しいセッションは開始されませんでした。",
        "member_required": "このセッションに参加したプレイヤーだけがこの操作を実行できます。",
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
        "ended": "세션을 종료하고 현재 세션 데이터를 삭제했습니다.",
        "end_failed": "세션을 종료하지 못했으며 데이터는 삭제되지 않았습니다.",
        "exported": "세션 로그를 내보냈습니다: {path}",
        "session_running": "이 대화에는 이미 진행 중인 세션이 있습니다. 먼저 /trpg_end 를 사용하고, 기록이 필요하면 그 전에 /trpg_export 를 사용하세요.",
        "start_cleanup_failed": "이전 세션 데이터를 삭제하지 못해 새 세션을 시작하지 않았습니다.",
        "member_required": "현재 TRPG 세션에 참가한 플레이어만 이 작업을 실행할 수 있습니다.",
        "max_turns": "이 세션은 최대 턴 수에 도달했습니다. /trpg_end 또는 /trpg_export 를 사용하세요.",
        "gm_failed": "GM 생성에 실패했습니다. 잠시 후 다시 시도하세요.",
        "roll_title": "주사위 결과",
        "dice_title": "판정 결과",
        "state_title": "상태 변경",
        "success": "성공",
        "failure": "실패",
    },
}


def message(language: str, key: str, **kwargs: Any) -> str:
    table = MESSAGES.get(language, MESSAGES["zh"])
    template = table.get(key, MESSAGES["zh"][key])
    return template.format(**kwargs)


def format_roll_text(language: str, result: Any) -> str:
    return (
        f"{message(language, 'roll_title')}: {result.expression}\n"
        f"rolls={result.rolls}, modifier={result.modifier}, total={result.total}"
    )


def turn_current_label(session: GameSession) -> str:
    player = current_turn_player(session)
    if player is None:
        return message(session.language, "turn_none")
    return player.character_name


def turn_advanced_message(session: GameSession) -> str:
    return message(
        session.language,
        "turn_advanced",
        current=turn_current_label(session),
    )


def prepend_turn_warning(warning: str, output: str) -> str:
    return "\n\n".join(part for part in (warning, output) if part)


def compose_action_output(
    language: str,
    narrative: str,
    dice_summary: str,
    state_summary: str,
    turn_summary: str,
    resolution: str,
) -> str:
    parts = [narrative.strip()]
    if dice_summary:
        parts.append(f"{message(language, 'dice_title')}\n{dice_summary}")
    if state_summary:
        parts.append(f"{message(language, 'state_title')}\n{state_summary}")
    if turn_summary:
        parts.append(f"{message(language, 'turn_control_title')}\n{turn_summary}")
    if resolution:
        parts.append(resolution.strip())
    return "\n\n".join(part for part in parts if part)


def format_turn_order(session: GameSession) -> str:
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
        f"{message(session.language, 'turn_title')}: {session.title}\n"
        f"Mode: {order.mode}\n"
        f"Phase: {order.phase}\n"
        f"Round: {order.round_count}\n"
        f"Paused: {paused}\n"
        f"Current: {turn_current_label(session)}\n"
        f"Queue:\n{queue}\n"
        f"Control Note: {order.control_note or '-'}"
    )


def format_pc(language: str, pc: PlayerCharacter) -> str:
    card = get_ruleset(pc.ruleset_id).format_character(pc)
    return f"{message(language, 'pc_title')}: {pc.character_name}\n{card}"


def format_status(session: GameSession) -> str:
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
        format_turn_order(session)
        if session.turn_order.enabled
        else message(session.language, "turn_disabled")
    )
    return (
        f"{message(session.language, 'status_title')}: {session.title}\n"
        f"Language: {session.language}\n"
        f"Ruleset: {session.ruleset_id}\n"
        f"Turn: {session.turn_count}\n"
        f"Scene: {scene}\n"
        f"Players:\n{players}\n"
        f"NPCs:\n{npcs}\n"
        f"Plot Threads:\n{threads}\n"
        f"Rule Nodes:\n{format_session_rule_nodes(session)}\n"
        f"{turn_order}\n"
        f"Summary: {session.history_summary or '-'}"
    )


def format_session_rule_nodes(session: GameSession) -> str:
    scenario = session.scenario_script if isinstance(session.scenario_script, dict) else {}
    nodes = [item for item in scenario.get("rule_nodes", []) if isinstance(item, dict)]
    if not nodes:
        return "- none"
    return "\n".join(
        f"- {str(node.get('title') or node.get('node_id') or 'untitled')}"
        for node in nodes
    )


def help_text(language: str) -> str:
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
