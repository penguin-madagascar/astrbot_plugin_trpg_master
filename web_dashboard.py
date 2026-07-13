from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import scenario_io
    from .astrbot_compat import error_response, file_response, json_response
    from .models import ScenarioScript
except ImportError:  # pragma: no cover - direct module loading outside package.
    import scenario_io
    from astrbot_compat import error_response, file_response, json_response
    from models import ScenarioScript


class WebDashboardService:
    def __init__(self, storage: Any, config: Any, data_dir: str | Path) -> None:
        self.storage = storage
        self.config = config
        self.data_dir = Path(data_dir)

    async def dashboard(self):
        scripts = await self.storage.load_scenario_scripts()
        session_loader = getattr(self.storage, "load_saved_sessions", None)
        sessions = await session_loader() if callable(session_loader) else []
        return json_response(
            {
                "settings_schema": scenario_io.load_config_schema(),
                "settings": dict(self.config),
                "scripts": scenario_io.script_list_payload(scripts),
                "knowledge_entries": scenario_io.knowledge_entries_payload(sessions),
            }
        )

    async def save_settings(self, request: Any):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("settings payload must be an object", status_code=400)
        try:
            updates = scenario_io.coerce_config_updates(
                scenario_io.load_config_schema(),
                payload,
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        self.config.update(updates)
        saver = getattr(self.config, "save_config", None)
        if callable(saver):
            saver()
        return json_response({"settings": dict(self.config)})

    async def list_scripts(self):
        scripts = await self.storage.load_scenario_scripts()
        return json_response({"scripts": scenario_io.script_list_payload(scripts)})

    async def get_script(self, script_id: str):
        scripts = await self.storage.load_scenario_scripts()
        script = scripts.get(str(script_id))
        if script is None:
            return error_response("script not found", status_code=404)
        return json_response({"script": script.to_dict()})

    async def save_script(self, request: Any):
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
        script.updated_at = scenario_io.current_timestamp()
        scripts[script.script_id] = script
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"script": script.to_dict()})

    async def delete_script(self, request: Any):
        payload = await request.json(default={})
        script_id = (
            str(payload.get("script_id") or "").strip()
            if isinstance(payload, dict)
            else ""
        )
        if not script_id:
            return error_response("script_id is required", status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        if script_id not in scripts:
            return error_response("script not found", status_code=404)
        del scripts[script_id]
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"deleted": script_id})

    async def import_scripts(self, request: Any):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("import payload must be an object", status_code=400)
        content = str(payload.get("content") or "")
        filename = str(payload.get("filename") or "")
        if not content.strip():
            return error_response("content is required", status_code=400)
        try:
            imported = scenario_io.parse_scenario_import(content, filename=filename)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        scripts = await self.storage.load_scenario_scripts()
        for script in imported:
            existing = scripts.get(script.script_id)
            if existing:
                script.created_at = existing.created_at
            script.updated_at = scenario_io.current_timestamp()
            scripts[script.script_id] = script
        await self.storage.save_scenario_scripts(scripts)
        return json_response({"scripts": [script.to_dict() for script in imported]})

    async def export_scripts(self):
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


def register_web_apis(context: Any, plugin_name: str, handlers: Any) -> None:
    register_api = getattr(context, "register_web_api", None)
    if not callable(register_api):
        return
    routes = [
        (f"/{plugin_name}/dashboard", handlers.web_dashboard, ["GET"], "TRPG dashboard"),
        (
            f"/{plugin_name}/settings/save",
            handlers.web_save_settings,
            ["POST"],
            "Save TRPG settings",
        ),
        (f"/{plugin_name}/scripts", handlers.web_list_scripts, ["GET"], "List scripts"),
        (
            f"/{plugin_name}/scripts/<script_id>",
            handlers.web_get_script,
            ["GET"],
            "Get script",
        ),
        (
            f"/{plugin_name}/scripts/save",
            handlers.web_save_script,
            ["POST"],
            "Save script",
        ),
        (
            f"/{plugin_name}/scripts/delete",
            handlers.web_delete_script,
            ["POST"],
            "Delete script",
        ),
        (
            f"/{plugin_name}/scripts/import",
            handlers.web_import_scripts,
            ["POST"],
            "Import scripts",
        ),
        (
            f"/{plugin_name}/scripts/export",
            handlers.web_export_scripts,
            ["GET"],
            "Export scripts",
        ),
    ]
    for route, handler, methods, description in routes:
        register_api(route, handler, methods, description)
