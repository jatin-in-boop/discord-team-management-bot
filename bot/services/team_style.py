"""Shared visual styling for team roles and channels."""

import colorsys
import unicodedata
from typing import Dict, Tuple

import discord


def role_colors(team_number: int) -> Tuple[discord.Color, discord.Color]:
    """Return stable, non-repeating colors for a team and its leader role.

    The golden-angle hue spread keeps adjacent team numbers visually far apart
    and does not repeat a fixed palette when more teams are created. The
    Team Leader color stays in the same hue family but is lighter and brighter.
    """
    if team_number < 1:
        raise ValueError("team_number must be positive")

    # 137.508° is the golden angle. A small hue step would make neighboring
    # teams look too similar; this distributes colors around the full wheel.
    hue = ((team_number - 1) * 137.508) % 360 / 360
    team_rgb = colorsys.hsv_to_rgb(hue, 0.72, 0.92)
    leader_rgb = colorsys.hsv_to_rgb(hue, 0.42, 1.0)

    def to_color(rgb: Tuple[float, float, float]) -> discord.Color:
        return discord.Color.from_rgb(*(round(channel * 255) for channel in rgb))

    return to_color(team_rgb), to_color(leader_rgb)


def role_names(team_number: int, sp_range: str) -> Tuple[str, str]:
    """Return readable, styled names for a team and its Team Leader role."""
    team_role = f"✦ 𝐓𝐄𝐀𝐌 {team_number} · {sp_range} SP"
    leader_role = (
        f"♛ 𝐓𝐄𝐀𝐌 𝐋𝐄𝐀𝐃𝐄𝐑 · 𝐓𝐄𝐀𝐌 {team_number} · {sp_range} SP"
    )
    return team_role, leader_role


def _italic_map() -> Dict[str, str]:
    """Build the Unicode Mathematical Italic alphabet once per process."""
    result: Dict[str, str] = {}
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
        try:
            result[char] = unicodedata.lookup(
                f"MATHEMATICAL ITALIC {'CAPITAL' if char.isupper() else 'SMALL'} "
                f"{char.upper()}"
            )
        except KeyError:
            # Unicode gives a handful of italic letters special code points.
            special = {
                "C": "ℭ",
                "H": "ℋ",
                "I": "ℐ",
                "R": "ℛ",
                "Z": "ℤ",
                "e": "ℯ",
                "g": "ℊ",
                "h": "ℎ",
                "o": "ℴ",
            }
            result[char] = special.get(char, char)
    return result


ITALIC_LETTERS = _italic_map()


def italic_text(text: str) -> str:
    """Render channel labels in the italic Unicode style shown in the reference."""
    return "".join(ITALIC_LETTERS.get(char, char) for char in text)


CHANNEL_LABELS = {
    "plan": ("╭・", "Plan"),
    "discussion": ("│・", "Team-Discussion"),
    "opponents": ("│・", "Opponents-IDs-and-Hangers"),
    "players": ("╰・", "Player-IDs-and-Hangers"),
}


def channel_name(channel_type: str) -> str:
    """Return the formatted Discord channel name for a team channel type."""
    prefix, label = CHANNEL_LABELS[channel_type]
    return prefix + italic_text(label)