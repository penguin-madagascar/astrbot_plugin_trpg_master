import asyncio

from web_dashboard import WebDashboardService


class FakeStorage:
    async def load_scenario_scripts(self):
        return {}

    async def load_saved_sessions(self):
        return []


def test_dashboard_service_builds_payload(tmp_path):
    service = WebDashboardService(
        storage=FakeStorage(),
        config={"max_turns": 20},
        data_dir=tmp_path,
    )

    payload = asyncio.run(service.dashboard())

    assert payload["settings"]["max_turns"] == 20
    assert payload["scripts"] == []
    assert payload["knowledge_entries"] == []
