from pathlib import Path

import pytest
from PIL import Image

from dice_gif import DiceGifTooLargeError, generate_dice_roll_gif
from models import DiceResult


def test_generate_dice_roll_gif_writes_animated_gif(tmp_path: Path):
    result = DiceResult(expression="2d6+1", rolls=[3, 5], modifier=1, total=9)

    gif_path = generate_dice_roll_gif(result, tmp_path)

    assert gif_path.exists()
    assert gif_path.suffix == ".gif"
    assert gif_path.stat().st_size > 0
    with Image.open(gif_path) as image:
        assert image.format == "GIF"
        assert image.is_animated
        assert image.n_frames > 1


def test_generate_dice_roll_gif_rejects_too_many_dice(tmp_path: Path):
    result = DiceResult(
        expression="13d6",
        rolls=[1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6, 1],
        modifier=0,
        total=43,
    )

    with pytest.raises(DiceGifTooLargeError):
        generate_dice_roll_gif(result, tmp_path)
