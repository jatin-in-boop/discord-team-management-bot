"""Shared visual styling for team roles and channels."""

import unicodedata
from typing import Dict, Tuple

import discord


# Each team gets a stable color pair based on its team number. The first color
# is the richer team color; the second is a brighter companion for the Team
# Leader role. These are intentionally curated jewel tones rather than the
# default Discord palette so the role list feels consistent and premium.
TEAM_COLOR_PAIRS = (
    (0x4F6BFF, 0xA7B7FF),  # royal blue
    (0x159CC9, 0x82D9F5),  # ocean blue
    (0x00A6A6, 0x67E4DC),  # teal
    (0x2DBE73, 0x91E8AE),  # emerald
    (0x84B82E, 0xD0ED76),  # lime
    (0xD99A25, 0xFFE08A),  # gold
    (0xF08C3A, 0xFFD09A),  # amber
    (0xE4634F, 0xFFADA0),  # coral
    (0xD9507F, 0xFFA2C0),  # rose
    (0x925CDB, 0xD0A9FF),  # violet
    (0x586BC9, 0xB1C0FF),  # indigo
    (0x2E9FBC, 0x98E4EF),  # aqua
)


def role_colors(team_number: int) -> Tuple[discord.Color, discord.Color]:
    """Return stable (team, team-leader) colors for a team number."""
    pair = TEAM_COLOR_PAIRS[(team_number - 1) % len(TEAM_COLOR_PAIRS)]
    return discord.Color(pair[0]), discord.Color(pair[1])


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