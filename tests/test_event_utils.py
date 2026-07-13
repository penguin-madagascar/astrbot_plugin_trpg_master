from event_utils import (
    block_default_llm,
    config_bool,
    event_message_text,
    one_line,
    safe_int,
    sender_id,
    sender_label,
    session_id,
    split_first,
    split_start_mode,
    stop_event,
)


class FakeEvent:
    unified_msg_origin = "group:42"

    def __init__(self) -> None:
        self.llm_blocked = False
        self.stopped = False

    def get_sender_id(self) -> str:
        return "user-7"

    def get_sender_name(self) -> str:
        return "Alice"

    def get_message_str(self) -> str:
        return "hello"

    def should_call_llm(self, blocked: bool) -> None:
        self.llm_blocked = blocked

    def stop_event(self) -> None:
        self.stopped = True


def test_event_identity_and_lifecycle_helpers():
    event = FakeEvent()

    assert session_id(event) == "group:42"
    assert sender_id(event) == "user-7"
    assert sender_label(event) == "Alice(user-7)"
    assert event_message_text(event) == "hello"

    block_default_llm(event)
    stop_event(event)

    assert event.llm_blocked is True
    assert event.stopped is True


def test_text_and_config_helpers():
    assert split_first("alpha beta gamma") == ("alpha", "beta gamma")
    assert split_start_mode("进阶 雾镇") == ("advanced", "雾镇")
    assert split_start_mode("雾镇") == ("", "雾镇")
    assert one_line(" a\n b ", 20) == "a b"
    assert safe_int("12", 3) == 12
    assert safe_int("invalid", 3) == 3
    assert config_bool({}, "enabled", True) is True
    assert config_bool({"enabled": "false"}, "enabled", True) is False
