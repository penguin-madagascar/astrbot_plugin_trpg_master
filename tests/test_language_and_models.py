from language import detect_language_from_theme
from models import GameSession, PlayerCharacter


def test_detect_language_from_theme_uses_chinese_for_empty_or_uncertain_text():
    assert detect_language_from_theme("") == "zh"
    assert detect_language_from_theme("??? 123") == "zh"


def test_detect_language_from_theme_identifies_common_scripts():
    assert detect_language_from_theme("被雾吞没的古镇") == "zh"
    assert detect_language_from_theme("A haunted lighthouse on the winter coast") == "en"
    assert detect_language_from_theme("霧の古い神社で始まる怪談") == "ja"
    assert detect_language_from_theme("안개 속의 오래된 저택") == "ko"


def test_game_session_serialization_preserves_language_and_players():
    session = GameSession.new(
        session_id="umo-1",
        title="Haunted Lighthouse",
        theme="Haunted Lighthouse",
        language="en",
    )
    session.players["42"] = PlayerCharacter(
        user_id="42",
        display_name="Dana",
        character_name="Mara",
        concept="Former sailor",
    )
    session.turn_count = 3

    restored = GameSession.from_dict(session.to_dict())

    assert restored.language == "en"
    assert restored.turn_count == 3
    assert restored.players["42"].character_name == "Mara"
