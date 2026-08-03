import discord
from typing import Optional
from app_logging.logger import get_logger
from bot.embeds.base import EmbedBuilder
from bot.views.management_panel import ManagementPanelView
from database.engine import get_db_session
from models.models import GuildConfiguration
from sqlalchemy import select

logger = get_logger(__name__)


class PanelUpdateService:
    """Reusable service to update the management panel without duplication."""

    def __init__(self, bot):
        self.bot = bot

    async def update_panel(self, guild: discord.Guild, embed: Optional[discord.Embed] = None) -> None:
        async with get_db_session() as session:
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == guild.id)
            )
            config = result.scalar_one_or_none()

            if not config or not config.management_channel_id or not config.management_message_id:
                return

            channel = guild.get_channel(config.management_channel_id)
            if not isinstance(channel, discord.TextChannel):
                return

            try:
                message = await channel.fetch_message(config.management_message_id)
                if embed is None:
                    embed = EmbedBuilder.management(
                        "Team Management",
                        "Professional tournament team management system.\n\n"
                        "Use the buttons below to manage teams."
                    )
                await message.edit(embed=embed, view=ManagementPanelView())
                logger.info("panel.updated", guild_id=guild.id)
            except discord.NotFound:
                logger.warning("panel.message_missing_on_update", guild_id=guild.id)
