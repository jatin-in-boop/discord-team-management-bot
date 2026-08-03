from discord import Embed, Color
from datetime import datetime
from typing import Optional


class EmbedBuilder:
    """Reusable embed builder for consistent UI across the bot."""

    DEFAULT_COLOR = 0x5865F2  # Blurple
    SUCCESS_COLOR = 0x57F287
    WARNING_COLOR = 0xFEE75C
    ERROR_COLOR = 0xED4245
    INFO_COLOR = 0x5865F2

    @staticmethod
    def base(title: str, description: Optional[str] = None, color: int = DEFAULT_COLOR) -> Embed:
        embed = Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Team Management Bot")
        return embed

    @staticmethod
    def success(title: str, description: Optional[str] = None) -> Embed:
        return EmbedBuilder.base(title, description, EmbedBuilder.SUCCESS_COLOR)

    @staticmethod
    def warning(title: str, description: Optional[str] = None) -> Embed:
        return EmbedBuilder.base(title, description, EmbedBuilder.WARNING_COLOR)

    @staticmethod
    def error(title: str, description: Optional[str] = None) -> Embed:
        return EmbedBuilder.base(title, description, EmbedBuilder.ERROR_COLOR)

    @staticmethod
    def info(title: str, description: Optional[str] = None) -> Embed:
        return EmbedBuilder.base(title, description, EmbedBuilder.INFO_COLOR)

    @staticmethod
    def management(title: str, description: Optional[str] = None) -> Embed:
        embed = EmbedBuilder.base(title, description, EmbedBuilder.DEFAULT_COLOR)
        embed.set_author(name="Team Management System")
        return embed
