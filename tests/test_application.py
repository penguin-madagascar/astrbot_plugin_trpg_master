import asyncio

from application import TRPGRuntime
from action_commands import ActionCommandService
from models import GameSession
from session_commands import SessionCommandService


class FakeStorage:
    def __init__(self, session):
        self.session = session

    async def load_session(self, _session_id):
        return self.session


class FakeOwner:
    def __init__(self, session):
        self.storage = FakeStorage(session)
        self.config = {}
        self.context = object()


def test_runtime_normalizes_loaded_running_session():
    session = GameSession.new(
        session_id="session-1",
        title="Fog",
        theme="Mystery",
        language="en",
    )
    session.play_mode = "invalid"
    event = type("Event", (), {"unified_msg_origin": "session-1"})()

    loaded = asyncio.run(TRPGRuntime(FakeOwner(session)).running_session(event))

    assert loaded is session
    assert loaded.play_mode == "advanced"
    assert loaded.feature_flags


def test_session_command_service_keeps_owner_dependencies_dynamic():
    owner = FakeOwner(None)
    service = SessionCommandService(owner, call_gm=lambda *args, **kwargs: None)

    replacement = object()
    owner.storage = replacement

    assert service.storage is replacement


def test_action_command_service_keeps_owner_dependencies_dynamic():
    owner = FakeOwner(None)
    service = ActionCommandService(
        owner,
        call_gm=lambda *args, **kwargs: None,
        call_command_agent=lambda *args, **kwargs: None,
    )

    replacement = object()
    owner.storage = replacement

    assert service.storage is replacement
