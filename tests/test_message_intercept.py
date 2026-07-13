import asyncio
import unittest
from unittest.mock import patch

import main
from main import LLMTRPGPlugin
from models import GameSession, PlayerCharacter
from turn_order import add_player_to_turn_order


class MessageInterceptTests(unittest.TestCase):
    def test_config_schema_exposes_command_agent_setting(self):
        schema = main._load_config_schema()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage()

        dashboard = asyncio.run(plugin.web_dashboard())
        updates = main._coerce_config_updates(
            schema,
            {"command_agent_enabled": "false"},
        )

        self.assertEqual(schema["command_agent_enabled"]["type"], "bool")
        self.assertIs(schema["command_agent_enabled"]["default"], True)
        self.assertIn("command_agent_enabled", dashboard["settings_schema"])
        self.assertEqual(updates, {"command_agent_enabled": False})

    def test_agent_converts_joined_player_text_to_status_without_gm(self):
        captured = {}

        async def fake_agent(context, event, *, prompt, system_prompt):
            captured["prompt"] = prompt
            return "/trpg_status"

        async def fail_call_gm(context, event, *, prompt, system_prompt):
            raise AssertionError("GM narration should not run for status command")

        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="查看状态")

        with patch.object(main, "call_command_agent", fake_agent), patch.object(
            main,
            "call_gm",
            fail_call_gm,
        ):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].startswith("跑团状态: 雾镇"))
        self.assertIn("/trpg_status", captured["prompt"])
        self.assertIn("查看状态", captured["prompt"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_agent_empty_match_falls_back_to_action_when_current_player_can_act(self):
        captured = {}

        async def fake_agent(context, event, *, prompt, system_prompt):
            return ""

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            captured["prompt"] = prompt
            return "Alice 查看脚印。\n```json\n{}\n```"

        session = make_session()
        plugin = LLMTRPGPlugin(
            context=object(),
            config={"command_agent_enabled": True, "strict_json_patch": True},
        )
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="查看脚印")

        with patch.object(main, "call_command_agent", fake_agent), patch.object(
            main,
            "call_gm",
            fake_call_gm,
        ):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 查看脚印。"])
        self.assertIn("玩家行动：查看脚印", captured["prompt"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_agent_allows_non_joined_user_to_join_but_not_act(self):
        async def join_agent(context, event, *, prompt, system_prompt):
            return "/trpg_join Bob 战士"

        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)
        join_event = FakeEvent(user_id="u2", sender_name="Morgan", message="我要加入 Bob 战士")

        with patch.object(main, "call_command_agent", join_agent):
            join_outputs = asyncio.run(_collect(plugin.trpg_message_intercept(join_event)))

        async def act_agent(context, event, *, prompt, system_prompt):
            return "/trpg_act 观察"

        act_event = FakeEvent(user_id="u3", sender_name="Casey", message="我观察")
        with patch.object(main, "call_command_agent", act_agent):
            act_outputs = asyncio.run(_collect(plugin.trpg_message_intercept(act_event)))

        self.assertEqual(join_outputs, ["角色已加入：Bob（HP 10 / SAN 50）"])
        self.assertIn("u2", session.players)
        self.assertEqual(act_outputs, ["当前阶段不允许执行该 TRPG 命令：/trpg_act"])
        self.assertTrue(join_event.stopped)
        self.assertTrue(act_event.stopped)

    def test_agent_rejects_out_of_turn_action_command(self):
        async def fake_agent(context, event, *, prompt, system_prompt):
            return "/trpg_act 观察门口"

        async def fail_call_gm(context, event, *, prompt, system_prompt):
            raise AssertionError("out-of-turn action should not reach GM")

        session = make_session()
        session.players["u2"] = PlayerCharacter(
            user_id="u2",
            display_name="Morgan",
            character_name="Bob",
            concept="战士",
        )
        session.turn_order.enabled = True
        add_player_to_turn_order(session, "u1")
        add_player_to_turn_order(session, "u2")
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u2", sender_name="Morgan", message="观察门口")

        with patch.object(main, "call_command_agent", fake_agent), patch.object(
            main,
            "call_gm",
            fail_call_gm,
        ):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["当前阶段不允许执行该 TRPG 命令：/trpg_act"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_direct_trpg_command_bypasses_agent(self):
        async def fail_agent(context, event, *, prompt, system_prompt):
            raise AssertionError("direct /trpg_* command should bypass agent")

        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_status")

        with patch.object(main, "call_command_agent", fail_agent):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].startswith("跑团状态: 雾镇"))
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_agent_does_not_run_after_session_end(self):
        async def fail_agent(context, event, *, prompt, system_prompt):
            raise AssertionError("ended session should not run command agent")

        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)
        end_event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_end")

        end_outputs = asyncio.run(_collect(plugin.trpg_message_intercept(end_event)))

        followup = FakeEvent(user_id="u1", sender_name="Dana", message="查看状态")
        with patch.object(main, "call_command_agent", fail_agent):
            followup_outputs = asyncio.run(_collect(plugin.trpg_message_intercept(followup)))

        self.assertEqual(end_outputs, ["跑团已结束，当前会话数据已删除。"])
        self.assertIsNone(plugin.storage.session)
        self.assertEqual(followup_outputs, [])
        self.assertFalse(followup.llm_blocked)
        self.assertFalse(followup.stopped)

    def test_running_session_cannot_be_restarted(self):
        async def fail_call_gm(context, event, *, prompt, system_prompt):
            raise AssertionError("running session restart must not call the GM")

        session = make_session()
        session.turn_count = 12
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u2", sender_name="Morgan", message="/trpg_start")

        with patch.object(main, "call_gm", fail_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_start(event, "")))

        self.assertEqual(
            outputs,
            ["当前会话已有进行中的跑团，请先使用 /trpg_end；如需保留记录，请先 /trpg_export。"],
        )
        self.assertIs(plugin.storage.session, session)
        self.assertEqual(plugin.storage.session.turn_count, 12)

    def test_non_member_cannot_act_end_or_export(self):
        async def fail_call_gm(context, event, *, prompt, system_prompt):
            raise AssertionError("non-member action must not call the GM")

        def fail_export(*args, **kwargs):
            raise AssertionError("non-member export must not write a file")

        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u2", sender_name="Morgan", message="")

        with patch.object(main, "call_gm", fail_call_gm):
            act_outputs = asyncio.run(_collect(plugin.trpg_act(event, "闯入")))
        end_outputs = asyncio.run(_collect(plugin.trpg_end(event)))
        with patch.object(main, "export_session_markdown", fail_export):
            export_outputs = asyncio.run(_collect(plugin.trpg_export(event)))

        expected = ["只有已加入当前跑团的玩家可以执行此操作。"]
        self.assertEqual(act_outputs, expected)
        self.assertEqual(end_outputs, expected)
        self.assertEqual(export_outputs, expected)
        self.assertIs(plugin.storage.session, session)
        self.assertEqual(session.turn_count, 0)

    def test_new_session_clears_legacy_ended_session(self):
        async def fake_call_gm(context, event, *, prompt, system_prompt):
            return "新团开场"

        session = make_session()
        session.status = "ended"
        plugin = LLMTRPGPlugin(context=object(), config={"default_theme": "新主题"})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u2", sender_name="Morgan", message="/trpg_start")

        with patch.object(main, "call_gm", fake_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_start(event, "")))

        self.assertEqual(outputs, ["新团开场"])
        self.assertEqual(plugin.storage.deleted_session_ids, ["session-1"])
        self.assertIsNotNone(plugin.storage.session)
        self.assertEqual(plugin.storage.session.title, "新主题")
        self.assertEqual(plugin.storage.session.status, "running")

    def test_end_failure_keeps_running_session(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(
            session,
            delete_error=RuntimeError("delete failed"),
        )
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_end")

        outputs = asyncio.run(_collect(plugin.trpg_end(event)))

        self.assertEqual(outputs, ["结束跑团失败，当前会话数据未删除。"])
        self.assertIs(plugin.storage.session, session)
        self.assertEqual(session.status, "running")

    def test_legacy_session_delete_failure_blocks_new_session(self):
        async def fail_call_gm(context, event, *, prompt, system_prompt):
            raise AssertionError("failed legacy cleanup must not call the GM")

        session = make_session()
        session.status = "ended"
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(
            session,
            delete_error=RuntimeError("delete failed"),
        )
        event = FakeEvent(user_id="u2", sender_name="Morgan", message="/trpg_start")

        with patch.object(main, "call_gm", fail_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_start(event, "")))

        self.assertEqual(outputs, ["无法清理旧跑团数据，新跑团未启动。"])
        self.assertIs(plugin.storage.session, session)
        self.assertEqual(session.status, "ended")

    def test_agent_invalid_outputs_error_and_stop(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": True})
        plugin.storage = FakeStorage(session)

        async def invalid_json_agent(context, event, *, prompt, system_prompt):
            raise ValueError("invalid command agent JSON")

        invalid_json_event = FakeEvent(user_id="u1", sender_name="Dana", message="查看状态")
        with patch.object(main, "call_command_agent", invalid_json_agent):
            invalid_json_outputs = asyncio.run(
                _collect(plugin.trpg_message_intercept(invalid_json_event))
            )

        async def outside_agent(context, event, *, prompt, system_prompt):
            return "/weather 上海"

        outside_event = FakeEvent(user_id="u1", sender_name="Dana", message="天气")
        with patch.object(main, "call_command_agent", outside_agent):
            outside_outputs = asyncio.run(_collect(plugin.trpg_message_intercept(outside_event)))

        async def empty_arg_agent(context, event, *, prompt, system_prompt):
            return "/trpg_act"

        empty_arg_event = FakeEvent(user_id="u1", sender_name="Dana", message="行动")
        with patch.object(main, "call_command_agent", empty_arg_agent):
            empty_arg_outputs = asyncio.run(
                _collect(plugin.trpg_message_intercept(empty_arg_event))
            )

        self.assertEqual(invalid_json_outputs, ["命令转换 Agent 返回无效 JSON。"])
        self.assertEqual(outside_outputs, ["当前阶段不允许执行该 TRPG 命令：/weather"])
        self.assertEqual(empty_arg_outputs, ["TRPG 命令缺少必要参数：/trpg_act"])
        self.assertTrue(invalid_json_event.stopped)
        self.assertTrue(outside_event.stopped)
        self.assertTrue(empty_arg_event.stopped)

    def test_command_agent_disabled_keeps_direct_action_behavior(self):
        async def fail_agent(context, event, *, prompt, system_prompt):
            raise AssertionError("disabled command agent should not run")

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            return "Alice 搜索房间。\n```json\n{}\n```"

        session = make_session()
        plugin = LLMTRPGPlugin(
            context=object(),
            config={"command_agent_enabled": False, "strict_json_patch": True},
        )
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="搜索房间")

        with patch.object(main, "call_command_agent", fail_agent), patch.object(
            main,
            "call_gm",
            fake_call_gm,
        ):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 搜索房间。"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_simple_mode_routes_joined_plain_text_and_accepts_plain_gm_reply(self):
        captured = {}

        async def fail_agent(context, event, *, prompt, system_prompt):
            raise AssertionError("simple mode should not run command agent")

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            captured["prompt"] = prompt
            return "Alice 查看房间。"

        session = make_session()
        session.play_mode = "simple"
        session.feature_flags = {
            "command_agent_enabled": False,
            "turn_order_enabled": False,
            "structured_patch_enabled": False,
            "dice_requests_enabled": False,
            "state_patch_enabled": False,
            "knowledge_enabled": False,
            "second_pass_resolution_enabled": False,
        }
        plugin = LLMTRPGPlugin(
            context=object(),
            config={"command_agent_enabled": True, "strict_json_patch": True},
        )
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="查看房间")

        with patch.object(main, "call_command_agent", fail_agent), patch.object(
            main,
            "call_gm",
            fake_call_gm,
        ):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 查看房间。"])
        self.assertIn("简易模式", captured["prompt"])
        self.assertNotIn("JSON 格式必须符合", captured["prompt"])
        self.assertEqual(session.turn_count, 1)
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_custom_mode_disabled_mechanics_do_not_apply_gm_patch(self):
        calls = []

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            calls.append(prompt)
            if len(calls) > 1:
                raise AssertionError("second pass should be disabled")
            return (
                "Alice 搜索房间。\n"
                "```json\n"
                "{\n"
                "  \"dice_requests\": [{\"id\": \"d1\", \"type\": \"skill_check\", "
                "\"actor\": \"Alice\", \"skill\": \"DEX\", \"dc\": 12}],\n"
                "  \"state_patches\": [{\"target\": \"pc:Alice\", \"op\": \"hp_delta\", "
                "\"value\": -3}],\n"
                "  \"knowledge_patches\": [{\"op\": \"add_fact\", \"text\": \"暗门存在\"}],\n"
                "  \"memory_notes\": [\"发现暗门\"]\n"
                "}\n"
                "```"
            )

        session = make_session()
        session.play_mode = "custom"
        session.feature_flags = {
            "command_agent_enabled": True,
            "turn_order_enabled": False,
            "structured_patch_enabled": True,
            "dice_requests_enabled": False,
            "state_patch_enabled": False,
            "knowledge_enabled": False,
            "second_pass_resolution_enabled": False,
        }
        plugin = LLMTRPGPlugin(context=object(), config={"allow_state_patch": True})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_act 搜索房间")

        with patch.object(main, "call_gm", fake_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 搜索房间。"])
        self.assertEqual(session.players["u1"].hp, 10)
        self.assertEqual(session.campaign_knowledge.facts, [])
        self.assertEqual(session.recent_events[-1], "Dana: 搜索房间 -> Alice 搜索房间。")
        self.assertEqual(len(calls), 1)

    def test_joined_player_plain_message_is_routed_to_trpg_act_and_stopped(self):
        captured = {}

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            captured["prompt"] = prompt
            return "Alice 观察房间。\n```json\n{}\n```"

        session = make_session()
        plugin = LLMTRPGPlugin(
            context=object(),
            config={"command_agent_enabled": False, "strict_json_patch": True},
        )
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="观察房间")

        with patch.object(main, "call_gm", fake_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 观察房间。"])
        self.assertIn("行动玩家：Alice", captured["prompt"])
        self.assertIn("玩家行动：观察房间", captured["prompt"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_joined_player_at_or_reply_text_is_routed_to_trpg_act(self):
        captured = {}

        async def fake_call_gm(context, event, *, prompt, system_prompt):
            captured["prompt"] = prompt
            return "Alice 推门。\n```json\n{}\n```"

        session = make_session()
        plugin = LLMTRPGPlugin(
            context=object(),
            config={"command_agent_enabled": False, "strict_json_patch": True},
        )
        plugin.storage = FakeStorage(session)
        event = FakeEvent(
            user_id="u1",
            sender_name="Dana",
            message="@bot 推门",
            is_at_or_wake_command=True,
        )

        with patch.object(main, "call_gm", fake_call_gm):
            outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["Alice 推门。"])
        self.assertIn("玩家行动：@bot 推门", captured["prompt"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_joined_player_known_trpg_command_is_handled_and_stopped(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_status")

        outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].startswith("跑团状态: 雾镇"))
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_joined_player_external_slash_command_is_not_intercepted(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/weather 上海")

        outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, [])
        self.assertFalse(event.llm_blocked)
        self.assertFalse(event.stopped)

    def test_joined_player_unknown_trpg_command_errors_and_stops(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="/trpg_unknown")

        outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["未知 TRPG 命令：/trpg_unknown"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)

    def test_non_joined_user_message_is_not_intercepted(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object(), config={"command_agent_enabled": False})
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u3", sender_name="Casey", message="我也看看")

        outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, [])
        self.assertFalse(event.llm_blocked)
        self.assertFalse(event.stopped)

    def test_joined_player_empty_message_errors_and_stops(self):
        session = make_session()
        plugin = LLMTRPGPlugin(context=object())
        plugin.storage = FakeStorage(session)
        event = FakeEvent(user_id="u1", sender_name="Dana", message="  ")

        outputs = asyncio.run(_collect(plugin.trpg_message_intercept(event)))

        self.assertEqual(outputs, ["无法处理空的跑团输入。"])
        self.assertTrue(event.llm_blocked)
        self.assertTrue(event.stopped)


def make_session() -> GameSession:
    session = GameSession.new(
        session_id="session-1",
        title="雾镇",
        theme="民俗恐怖",
        language="zh",
    )
    session.players["u1"] = PlayerCharacter(
        user_id="u1",
        display_name="Dana",
        character_name="Alice",
        concept="调查员",
    )
    return session


class FakeEvent:
    unified_msg_origin = "session-1"

    def __init__(
        self,
        *,
        user_id: str,
        sender_name: str,
        message: str,
        is_at_or_wake_command: bool = False,
    ) -> None:
        self.user_id = user_id
        self.sender_name = sender_name
        self.message_str = message
        self.is_at_or_wake_command = is_at_or_wake_command
        self.call_llm = False
        self.stopped = False
        self.should_call_llm_values = []

    @property
    def llm_blocked(self) -> bool:
        return self.call_llm is True or self.should_call_llm_values == [True]

    def get_message_str(self) -> str:
        return self.message_str

    def get_sender_id(self) -> str:
        return self.user_id

    def get_sender_name(self) -> str:
        return self.sender_name

    def should_call_llm(self, value: bool) -> None:
        self.should_call_llm_values.append(value)
        self.call_llm = value

    def stop_event(self) -> None:
        self.stopped = True

    def plain_result(self, text: str) -> str:
        return text


class FakeStorage:
    def __init__(
        self,
        session: GameSession | None = None,
        *,
        delete_error: Exception | None = None,
    ) -> None:
        self.session = session
        self.deleted_session_ids = []
        self.delete_error = delete_error

    async def load_scenario_scripts(self):
        return {}

    async def load_session(self, session_id: str) -> GameSession | None:
        return self.session

    async def save_session(self, session: GameSession) -> None:
        self.session = session

    async def delete_session(self, session_id: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted_session_ids.append(session_id)
        self.session = None


async def _collect(generator):
    results = []
    async for item in generator:
        results.append(item)
    return results
