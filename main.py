from __future__ import annotations

from pathlib import Path

try:
    from .action_commands import ActionCommandService
    from .application import TRPGRuntime
    from .astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Star,
        StarTools,
        filter,
        register,
        request,
    )
except ImportError:  # pragma: no cover - direct module loading outside package.
    from action_commands import ActionCommandService
    from application import TRPGRuntime
    from astrbot_compat import (
        AstrBotConfig,
        AstrMessageEvent,
        Context,
        GreedyStr,
        Star,
        StarTools,
        filter,
        register,
        request,
    )

try:
    from .session_commands import SessionCommandService
    from . import web_dashboard
    from .gm import call_command_agent, call_gm
    from .storage import SessionStorage
except ImportError:  # pragma: no cover - direct module loading outside package.
    from session_commands import SessionCommandService
    import web_dashboard
    from gm import call_command_agent, call_gm
    from storage import SessionStorage


PLUGIN_NAME = "astrbot_plugin_trpg_master"
PLUGIN_VERSION = "0.1.0"
PLUGIN_REPOSITORY = "https://github.com/penguin-madagascar/astrbot_plugin_trpg_master"
PLUGIN_DESCRIPTION = "LLM 驱动的 TRPG/跑团插件，Python 负责骰子、规则判定、状态和日志。"

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
        service = ActionCommandService(
            self,
            call_gm=call_gm,
            call_command_agent=call_command_agent,
        )
        async for item in service.intercept(event):
            yield item

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
        service = ActionCommandService(
            self,
            call_gm=call_gm,
            call_command_agent=call_command_agent,
        )
        async for item in service.act(event, action):
            yield item

    @filter.command("trpg_roll", desc="掷基础骰子表达式。")
    async def trpg_roll(self, event: AstrMessageEvent, expression: GreedyStr = ""):
        service = ActionCommandService(
            self,
            call_gm=call_gm,
            call_command_agent=call_command_agent,
        )
        async for item in service.roll(event, expression):
            yield item

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
