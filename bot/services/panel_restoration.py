import discord
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import GuildConfiguration
from sqlalchemy import select
from bot.views.management_panel import ManagementPanelView
from bot.embeds.base import EmbedBuilder

logger = get_logger(__name__)


class PanelRestorationService:
    def __init__(self, bot):
        self.bot = bot

    async def restore_guild_panel(self, guild: discord.Guild):
        async with get_db_session() as session:
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == guild.id)
            )
            config = result.scalar_one_or_none()

            if not config or not config.setup_complete:
                return

            channel = guild.get_channel(config.management_channel_id) if config.management_channel_id else None
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning("restoration.channel_missing", guild_id=guild.id)
                return

            try:
                message = await channel.fetch_message(config.management_message_id)
                # Re-attach view if message exists
                await message.edit(view=ManagementPanelView())
                logger.info("restoration.panel_restored", guild_id=guild.id, message_id=message.id)
            except discord.NotFound:
                logger.warning("restoration.message_missing", guild_id=guild.id)
                # Recreate panel
                from bot.services.guild_setup import GuildSetupService
                setup = GuildSetupService(self.bot)
                await setup._get_or_create_panel(channel)
                logger.info("restoration.panel_recreated", guild_id=guild.id)
            except Exception as e:
                logger.error("restoration.error", guild_id=guild.id, error=str(e))
