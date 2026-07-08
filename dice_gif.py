from __future__ import annotations

import math
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .models import DiceResult
except ImportError:  # pragma: no cover - direct test import outside package.
    from models import DiceResult


MAX_GIF_DICE = 12
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 360
DEFAULT_FRAMES = 24
DEFAULT_DURATION_MS = 45


class DiceGifError(RuntimeError):
    """Base error for dice GIF generation."""


class DiceGifTooLargeError(DiceGifError):
    """Raised when a dice result is too large to render as a chat-friendly GIF."""


@dataclass
class _DieBody:
    roll: int
    x: float
    y: float
    vx: float
    vy: float
    size: float
    yaw: float
    pitch: float
    roll_angle: float
    wyaw: float
    wpitch: float
    wroll: float
    color: tuple[int, int, int]


def generate_dice_roll_gif(
    result: DiceResult,
    output_dir: Path,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    frame_count: int = DEFAULT_FRAMES,
    duration_ms: int = DEFAULT_DURATION_MS,
    max_dice: int = MAX_GIF_DICE,
) -> Path:
    if not result.rolls:
        raise DiceGifError("cannot render an empty dice result")
    if len(result.rolls) > max_dice:
        raise DiceGifTooLargeError(
            f"GIF dice count limit is {max_dice}, got {len(result.rolls)}"
        )

    try:
        from PIL import Image as PILImage
    except ModuleNotFoundError as exc:
        raise DiceGifError("Pillow is required to render dice GIFs") from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bodies = _initial_bodies(result.rolls, width, height)
    frames = [
        _render_frame(PILImage, result, bodies, width, height, frame, frame_count)
        for frame in range(frame_count)
    ]
    filename = f"dice_{time.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}.gif"
    path = output_dir / filename
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return path


def _initial_bodies(
    rolls: list[int],
    width: int,
    height: int,
) -> list[_DieBody]:
    count = len(rolls)
    size = max(30, min(62, int(150 / math.sqrt(count + 1))))
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    spacing_x = width / (cols + 1)
    spacing_y = (height - 80) / (rows + 1)
    palette = [
        (218, 64, 72),
        (58, 126, 214),
        (52, 159, 105),
        (226, 155, 45),
        (128, 88, 202),
        (48, 168, 188),
    ]
    bodies: list[_DieBody] = []
    for index, value in enumerate(rolls):
        col = index % cols
        row = index // cols
        base = palette[index % len(palette)]
        bodies.append(
            _DieBody(
                roll=int(value),
                x=spacing_x * (col + 1),
                y=spacing_y * (row + 1) + 12,
                vx=_rand_float(-6.0, 6.0),
                vy=_rand_float(-5.0, 2.5),
                size=size,
                yaw=_rand_float(0.0, math.tau),
                pitch=_rand_float(0.0, math.tau),
                roll_angle=_rand_float(0.0, math.tau),
                wyaw=_rand_float(-0.34, 0.34),
                wpitch=_rand_float(-0.30, 0.30),
                wroll=_rand_float(-0.38, 0.38),
                color=_jitter_color(base),
            )
        )
    return bodies


def _render_frame(
    image_module: Any,
    result: DiceResult,
    bodies: list[_DieBody],
    width: int,
    height: int,
    frame: int,
    frame_count: int,
) -> Any:
    from PIL import ImageDraw, ImageFont

    progress = frame / max(frame_count - 1, 1)
    image = image_module.new("RGB", (width, height), (27, 30, 40))
    draw = ImageDraw.Draw(image)
    _draw_background(draw, width, height)

    for _ in range(2):
        _step_physics(bodies, width, height, progress)

    for body in sorted(bodies, key=lambda item: item.y):
        display = body.roll if progress > 0.74 else max(1, body.roll + int(math.sin(frame + body.x) * 3))
        _draw_die(draw, body, display, progress)

    _draw_footer(draw, result, width, height, progress, ImageFont)
    return image


def _step_physics(
    bodies: list[_DieBody],
    width: int,
    height: int,
    progress: float,
) -> None:
    floor = height - 78
    damping = 0.93 if progress < 0.78 else 0.74
    gravity = 0.58 if progress < 0.82 else 0.18
    for body in bodies:
        body.vy += gravity
        body.x += body.vx
        body.y += body.vy
        body.yaw += body.wyaw * (1.15 - progress)
        body.pitch += body.wpitch * (1.15 - progress)
        body.roll_angle += body.wroll * (1.15 - progress)

        radius = body.size * 0.82
        if body.x < radius:
            body.x = radius
            body.vx = abs(body.vx) * damping
        elif body.x > width - radius:
            body.x = width - radius
            body.vx = -abs(body.vx) * damping
        if body.y > floor - radius:
            body.y = floor - radius
            body.vy = -abs(body.vy) * damping
            body.vx *= 0.88
        elif body.y < radius + 8:
            body.y = radius + 8
            body.vy = abs(body.vy) * damping

    for left_index, left in enumerate(bodies):
        for right in bodies[left_index + 1 :]:
            dx = right.x - left.x
            dy = right.y - left.y
            distance = math.hypot(dx, dy) or 1.0
            minimum = (left.size + right.size) * 0.72
            if distance >= minimum:
                continue
            nx = dx / distance
            ny = dy / distance
            overlap = (minimum - distance) / 2
            left.x -= nx * overlap
            left.y -= ny * overlap
            right.x += nx * overlap
            right.y += ny * overlap
            left.vx, right.vx = right.vx * 0.82, left.vx * 0.82
            left.vy, right.vy = right.vy * 0.82, left.vy * 0.82


def _draw_background(draw: Any, width: int, height: int) -> None:
    for y in range(height):
        shade = int(32 + y / height * 34)
        draw.line([(0, y), (width, y)], fill=(shade, shade + 2, shade + 10))
    table_y = height - 58
    draw.rounded_rectangle(
        (24, table_y, width - 24, height - 16),
        radius=18,
        fill=(39, 45, 55),
        outline=(72, 79, 92),
        width=2,
    )


def _draw_die(
    draw: Any,
    body: _DieBody,
    display_value: int,
    progress: float,
) -> None:
    shadow_radius = body.size * (0.82 + 0.08 * math.sin(progress * math.pi))
    draw.ellipse(
        (
            body.x - shadow_radius,
            body.y + body.size * 0.52,
            body.x + shadow_radius,
            body.y + body.size * 0.86,
        ),
        fill=(18, 20, 27),
    )

    vertices = [
        (-1, -1, -1),
        (1, -1, -1),
        (1, 1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (1, 1, 1),
        (-1, 1, 1),
    ]
    projected: list[tuple[float, float, float]] = []
    for vertex in vertices:
        x, y, z = _rotate(vertex, body.yaw, body.pitch, body.roll_angle)
        x *= body.size / 2
        y *= body.size / 2
        z *= body.size / 2
        scale = 260 / (260 + z)
        projected.append((body.x + x * scale, body.y + y * scale, z))

    faces = [
        (0, 1, 2, 3, 0.76),
        (4, 5, 6, 7, 1.05),
        (0, 1, 5, 4, 0.90),
        (2, 3, 7, 6, 0.67),
        (1, 2, 6, 5, 0.84),
        (0, 3, 7, 4, 0.58),
    ]
    face_order = sorted(
        faces,
        key=lambda face: sum(projected[index][2] for index in face[:4]) / 4,
    )
    for face in face_order:
        points = [(projected[index][0], projected[index][1]) for index in face[:4]]
        draw.polygon(points, fill=_shade(body.color, face[4]))
        draw.line(points + [points[0]], fill=(238, 240, 245), width=2)

    _draw_center_number(draw, body, display_value)


def _draw_center_number(draw: Any, body: _DieBody, value: int) -> None:
    from PIL import ImageFont

    font = _load_font(ImageFont, max(16, int(body.size * 0.42)))
    text = str(value)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = body.x - text_width / 2
    y = body.y - text_height / 2 - body.size * 0.03
    draw.text((x + 2, y + 2), text, font=font, fill=(25, 27, 34))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))


def _draw_footer(
    draw: Any,
    result: DiceResult,
    width: int,
    height: int,
    progress: float,
    font_module: Any,
) -> None:
    font = _load_font(font_module, 18)
    small = _load_font(font_module, 13)
    rolls = ", ".join(str(value) for value in result.rolls)
    modifier = f"{result.modifier:+d}" if result.modifier else "+0"
    text = f"{result.expression}  rolls [{rolls}]  modifier {modifier}  total {result.total}"
    alpha = min(1.0, max(0.0, (progress - 0.55) / 0.35))
    fill = tuple(int(170 + alpha * 70) for _ in range(3))
    bbox = draw.textbbox((0, 0), text, font=font)
    x = max(16, (width - (bbox[2] - bbox[0])) / 2)
    draw.text((x + 1, height - 44), text, font=font, fill=(16, 18, 24))
    draw.text((x, height - 45), text, font=font, fill=fill)
    draw.text((18, 15), "TRPG DICE ROLL", font=small, fill=(152, 166, 190))


def _rotate(
    point: tuple[float, float, float],
    yaw: float,
    pitch: float,
    roll_angle: float,
) -> tuple[float, float, float]:
    x, y, z = point
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp - z * sp, y * sp + z * cp
    cr, sr = math.cos(roll_angle), math.sin(roll_angle)
    x, y = x * cr - y * sr, x * sr + y * cr
    return x, y, z


def _load_font(font_module: Any, size: int) -> Any:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        try:
            return font_module.truetype(candidate, size=size)
        except OSError:
            continue
    return font_module.load_default()


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)


def _jitter_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(max(30, min(245, channel + secrets.randbelow(31) - 15)) for channel in color)


def _rand_float(low: float, high: float) -> float:
    return low + (high - low) * (secrets.randbelow(10_000) / 10_000)
