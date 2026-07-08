import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from models import CharacterPreset
from storage import SessionStorage


class NoKVContext:
    pass


def test_storage_saves_and_loads_presets_via_file_fallback():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        preset = CharacterPreset(
            name="艾莉丝",
            character_name="Alice",
            concept="敏捷的游侠",
            hp=12,
            san=48,
            inventory=["银钥匙"],
        )

        asyncio.run(storage.save_presets("u1", {"艾莉丝": preset}))
        loaded = asyncio.run(storage.load_presets("u1"))

        assert loaded == {"艾莉丝": preset}


def test_storage_keeps_presets_isolated_by_user_id():
    with TemporaryDirectory() as tmp:
        storage = SessionStorage(NoKVContext(), Path(tmp))
        preset = CharacterPreset(
            name="艾莉丝",
            character_name="Alice",
            concept="敏捷的游侠",
        )

        asyncio.run(storage.save_presets("u1", {"艾莉丝": preset}))

        assert asyncio.run(storage.load_presets("u2")) == {}
