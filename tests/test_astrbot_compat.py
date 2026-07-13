from astrbot_compat import (
    AstrBotConfig,
    Image,
    MessageChain,
    Star,
    StarTools,
    error_response,
    file_response,
    json_response,
)


def test_local_astrbot_compatibility_surface_is_usable(tmp_path):
    assert AstrBotConfig is dict
    assert issubclass(MessageChain, list)
    assert Star(context="ctx").context == "ctx"
    assert StarTools.get_data_dir("demo").as_posix().endswith("plugin_data/demo")
    assert Image.fromFileSystem(tmp_path / "roll.gif").endswith("roll.gif")
    assert json_response({"ok": True}) == {"ok": True}
    assert error_response("bad", 422)["status_code"] == 422
    assert file_response(tmp_path / "log.md")["filename"] == "log.md"
