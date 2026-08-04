from __future__ import annotations

import asyncio
import io
from typing import Any

from app_logging.logger import get_logger
from bot.services.pulse_service import DEFAULT_BANDS, band_for_level

logger = get_logger(__name__)

CARD_FILENAME = "guild-pulse-top-five.png"
CARD_WIDTH = 1200


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    if not bold:
        candidates = candidates[::-1]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _initials(name: str) -> str:
    parts = [part for part in name.replace("_", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


def _rgb(value: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, int):
        return tuple((value >> shift) & 0xFF for shift in (16, 8, 0))
    return fallback


async def _avatar_bytes(member: Any) -> bytes | None:
    try:
        return await member.display_avatar.read()
    except Exception:
        return None


def _circle_avatar(
    canvas: Any,
    member: Any,
    raw: bytes | None,
    center: tuple[int, int],
    diameter: int,
    *,
    accent: tuple[int, int, int],
) -> None:
    from PIL import Image, ImageDraw

    x, y = center
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter, diameter), fill=255)
    if raw:
        try:
            avatar = Image.open(io.BytesIO(raw)).convert("RGB")
            avatar.thumbnail((diameter, diameter), Image.Resampling.LANCZOS)
            square = Image.new("RGB", (diameter, diameter), accent)
            square.paste(
                avatar,
                ((diameter - avatar.width) // 2, (diameter - avatar.height) // 2),
            )
        except Exception:
            square = None
    else:
        square = None
    if square is None:
        square = Image.new("RGB", (diameter, diameter), accent)
        draw = ImageDraw.Draw(square)
        label = _initials(getattr(member, "display_name", "Member"))
        font = _font(max(20, diameter // 3), bold=True)
        box = draw.textbbox((0, 0), label, font=font)
        draw.text(
            ((diameter - (box[2] - box[0])) / 2, (diameter - (box[3] - box[1])) / 2 - box[1]),
            label,
            font=font,
            fill=(245, 248, 255),
        )
    canvas.paste(square, (x - diameter // 2, y - diameter // 2), mask)
    ImageDraw.Draw(canvas).ellipse(
        (x - diameter // 2 - 5, y - diameter // 2 - 5, x + diameter // 2 + 5, y + diameter // 2 + 5),
        outline=accent,
        width=5,
    )


def _rounded(draw: Any, box: tuple[int, int, int, int], fill: tuple[int, int, int], radius: int = 22, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _fit_text(draw: Any, text: str, font: Any, max_width: int) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    suffix = "…"
    while len(text) > 1 and draw.textbbox((0, 0), text + suffix, font=font)[2] > max_width:
        text = text[:-1]
    return text + suffix


async def render_top_five_card(
    guild: Any,
    rows: list[Any],
    settings: Any,
    viewer_id: int | None = None,
    viewer_profile: dict[str, Any] | None = None,
) -> bytes:
    """Render the mobile-friendly PLAYER LEGACY Top 5 card."""
    from PIL import Image, ImageDraw, ImageFilter

    rows = rows[:5]
    bands = settings.band_config or DEFAULT_BANDS
    bg = (9, 14, 27)
    panel = (20, 29, 48)
    panel_2 = (26, 37, 60)
    ink = (239, 244, 255)
    muted = (150, 166, 193)
    teal = (45, 212, 168)
    violet = (139, 124, 246)
    gold = (247, 193, 73)

    # Keep the public and personal versions on the same canvas.  The public
    # card still needs room for the full PLAYER LEGACY path; shortening it
    # caused the bottom milestone rail to overlap the current role label when
    # Discord scaled the attachment down on mobile.
    height = 1510
    image = Image.new("RGB", (CARD_WIDTH, height), bg)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-220, -250, 610, 560), fill=(45, 212, 168, 55))
    glow_draw.ellipse((720, 180, 1420, 840), fill=(139, 124, 246, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)

    small = _font(24)
    label = _font(26, bold=True)
    title = _font(62, bold=True)
    hero = _font(42, bold=True)
    value = _font(32, bold=True)
    body = _font(28)
    tiny = _font(21)

    draw.text((70, 55), "PLAYER LEGACY  /  LEADERBOARD", font=small, fill=teal)
    draw.text((70, 94), "TOP FIVE", font=title, fill=ink)
    draw.text(
        (70, 174),
        "The people moving the room forward.",
        font=body,
        fill=muted,
    )
    draw.text(
        (CARD_WIDTH - 70, 75),
        f"{len(rows):02d} PLAYERS",
        font=label,
        fill=gold,
        anchor="ra",
    )
    draw.line((70, 230, CARD_WIDTH - 70, 230), fill=(53, 70, 100), width=2)

    avatar_data = await asyncio.gather(
        *[
            _avatar_bytes(guild.get_member(row.member_id))
            if guild.get_member(row.member_id)
            else asyncio.sleep(0, result=None)
            for row in rows
        ]
    )

    # The podium is deliberately asymmetrical: first place is the anchor,
    # while second and third orbit it as supporting signals.
    podium_y = 285
    positions = [
        (CARD_WIDTH // 2, podium_y + 20, 166, gold),
        (220, podium_y + 86, 124, (181, 198, 222)),
        (980, podium_y + 86, 124, (190, 135, 91)),
    ]
    podium_cards = [
        (0, (390, podium_y - 15, 810, podium_y + 360)),
        (1, (65, podium_y + 25, 375, podium_y + 340)),
        (2, (825, podium_y + 25, 1135, podium_y + 340)),
    ]
    for position, card in podium_cards:
        if position >= len(rows):
            continue
        row = rows[position]
        member = guild.get_member(row.member_id)
        name = member.display_name if member else f"Member {row.member_id}"
        band = band_for_level(row.current_level, bands)
        accent = _rgb(band.get("color"), teal)
        _rounded(draw, card, panel_2 if position == 0 else panel, 28, outline=accent, width=3)
        cx, cy, diameter, medal_color = positions[position]
        _circle_avatar(image, member or type("Member", (), {"display_name": name})(), avatar_data[position], (cx, cy), diameter, accent=accent)
        draw.text((cx, cy + diameter // 2 + 20), f"#{position + 1}", font=hero if position == 0 else value, fill=medal_color, anchor="ma")
        draw.text((cx, cy + diameter // 2 + 76), _fit_text(draw, name, label, 350), font=label, fill=ink, anchor="ma")
        draw.text((cx, cy + diameter // 2 + 115), f"LEVEL {row.current_level}  ·  {row.total_xp:,} XP", font=tiny, fill=muted, anchor="ma")
        draw.text((cx, cy + diameter // 2 + 151), band.get("name", "Milestone").upper(), font=tiny, fill=accent, anchor="ma")

    list_top = 705
    draw.text((70, list_top), "RISING PLAYERS", font=label, fill=teal)
    draw.text((CARD_WIDTH - 70, list_top), "RANK  /  LEVEL  /  XP", font=tiny, fill=muted, anchor="ra")
    for offset, row in enumerate(rows[3:5], 3):
        y = list_top + 52 + (offset - 3) * 112
        member = guild.get_member(row.member_id)
        name = member.display_name if member else f"Member {row.member_id}"
        band = band_for_level(row.current_level, bands)
        accent = _rgb(band.get("color"), teal)
        _rounded(draw, (70, y, CARD_WIDTH - 70, y + 88), panel, 18)
        _circle_avatar(image, member or type("Member", (), {"display_name": name})(), avatar_data[offset], (123, y + 44), 62, accent=accent)
        draw.text((180, y + 18), f"#{offset + 1}  {_fit_text(draw, name, label, 440)}", font=label, fill=ink)
        draw.text((180, y + 52), band.get("name", "Milestone"), font=tiny, fill=accent)
        draw.text((CARD_WIDTH - 100, y + 21), f"L{row.current_level}", font=value, fill=ink, anchor="ra")
        draw.text((CARD_WIDTH - 100, y + 56), f"{row.total_xp:,} XP", font=tiny, fill=muted, anchor="ra")

    path_top = 1000
    if viewer_profile:
        path_title = f"YOUR PLAYER LEGACY PATH  /  RANK #{viewer_profile['rank']}"
        current_level = viewer_profile["level"]
        current_xp = viewer_profile["current"]
        needed = viewer_profile["needed"]
        path_band = viewer_profile["band"].get("name", "Milestone")
    else:
        path_title = "PLAYER LEGACY PATH  /  NEXT MILESTONE"
        current_level, current_xp, needed = 1, 0, 1
        path_band = bands[0].get("name", "Milestone") if bands else "Milestone"

    path_bottom = height - 60
    _rounded(draw, (70, path_top, CARD_WIDTH - 70, path_bottom), panel_2, 28, outline=(48, 67, 96), width=2)
    draw.text((105, path_top + 34), path_title, font=label, fill=violet)
    draw.text((105, path_top + 78), "CURRENT MILESTONE", font=tiny, fill=muted)
    draw.text((105, path_top + 108), path_band.upper(), font=hero, fill=ink)
    draw.text((CARD_WIDTH - 105, path_top + 115), f"LEVEL {current_level}", font=value, fill=gold, anchor="ra")
    bar_x, bar_y, bar_w, bar_h = 105, path_top + 190, CARD_WIDTH - 210, 28
    _rounded(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), (11, 18, 32), 14)
    progress = min(1.0, current_xp / max(1, needed))
    if progress:
        _rounded(draw, (bar_x, bar_y, bar_x + max(18, int(bar_w * progress)), bar_y + bar_h), teal, 14)
    draw.text((bar_x, bar_y + 50), f"{current_xp:,} XP earned", font=tiny, fill=ink)
    draw.text((bar_x + bar_w, bar_y + 50), f"{needed:,} XP to next level", font=tiny, fill=muted, anchor="ra")

    milestones = [band for band in bands if int(band.get("max", 0)) >= current_level][:4]
    if not milestones:
        milestones = bands[:4]
    # The rail is a separate row below the progress readout.  Keep it
    # relative to the path panel rather than anchoring it to the overall
    # image height, so both public and personal cards remain stable.
    rail_title_y = bar_y + 112
    step_y = rail_title_y + 54
    draw.text((105, rail_title_y), "NEXT MILESTONES", font=tiny, fill=muted)
    rail_left, rail_right = 155, CARD_WIDTH - 155
    rail_span = max(1, len(milestones) - 1)
    for index, milestone in enumerate(milestones):
        x = (
            (rail_left + rail_right) // 2
            if len(milestones) == 1
            else rail_left + round(index * (rail_right - rail_left) / rail_span)
        )
        color = _rgb(milestone.get("color"), teal)
        draw.ellipse((x - 13, step_y - 13, x + 13, step_y + 13), fill=color)
        if index < len(milestones) - 1:
            next_x = (
                (rail_left + rail_right) // 2
                if len(milestones) == 1
                else rail_left + round((index + 1) * (rail_right - rail_left) / rail_span)
            )
            draw.line((x + 16, step_y, next_x - 16, step_y), fill=(71, 89, 119), width=4)
        draw.text(
            (x, step_y + 28),
            f"L{milestone.get('min', 1)}",
            font=label,
            fill=ink,
            anchor="ma",
        )
        draw.text(
            (x, step_y + 55),
            _fit_text(
                draw,
                milestone.get("name", "Milestone").upper(),
                tiny,
                max(120, (rail_right - rail_left) // max(1, rail_span) - 24),
            ),
            font=tiny,
            fill=muted,
            anchor="ma",
        )

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()