"""Shared visual styling for team roles and channels."""

import unicodedata
from typing import Dict, Tuple

import discord


# Each team gets a stable color pair based on its team number. The second color
# is a brighter companion for the Team Leader role.
TEAM_COLOR_PAIRS = (
    (0x5865F2, 0x9B9EFF),  # blurple
    (0x00AFF4, 0x66D7FF),  # blue
    (0x1ABC9C, 0x5DE0C2),  # teal
    (0x57F287, 0x8FF5A8),  # green
    (0xFEE75C, 0xFFE99A),  # yellow
    (0xE67E22, 0xFFAD5C),  # orange
    (0xED4245, 0xF47779),  # red
    (0xEB459E, 0xF47BBB),  # pink
    (0x9B59B6, 0xC084D8),  # purple
)


def role_colors(team_number: int) -> Tuple[discord.Color, discord.Color]:
    """Return stable (team, team-leader) colors for a team number."""
    pair = TEAM_COLOR_PAIRS[(team_number - 1) % len(TEAM_COLOR_PAIRS)]
    return discord.Color(pair[0]), discord.Color(pair[1])


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