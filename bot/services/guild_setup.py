import discord
from typing import Optional
from config.settings import get_settings
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import Guild as DbGuild, GuildConfiguration
from sqlalchemy import select

logger = get_logger(__name__)
settings = get_settings()


class GuildSetupService:
    def __init__(self, bot):
        self.bot = bot
        self.management_category_name = "🤖 Team Management"
        self.management_channel_name = "team-management"

    async def setup_guild(self, guild: discord.Guild) -> None:
        logger.info("guild.setup.start", guild_id=guild.id)

        async with get_db_session() as session:
            # Ensure guild record exists
            result = await session.execute(
                select(DbGuild).where(DbGuild.guild_id == guild.id)
            )
            db_guild = result.scalar_one_or_none()

            if not db_guild:
                db_guild = DbGuild(guild_id=guild.id, name=guild.name)
                session.add(db_guild)
                await session.flush()

            # Check existing configuration
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == guild.id)
            )
            config = result.scalar_one_or_none()

            if config and config.setup_complete:
                logger.info("guild.setup.already_configured", guild_id=guild.id)
                return

            # Create or reuse category
            category = await self._get_or_create_category(guild)

            # Create or reuse channel
            channel = await self._get_or_create_channel(guild, category)

            # Create or reuse panel message
            message = await self._get_or_create_panel(channel)

            # Save configuration
            if not config:
                config = GuildConfiguration(
                    guild_id=guild.id,
                    management_category_id=category.id,
                    management_channel_id=channel.id,
                    management_message_id=message.id,
                    setup_complete=True,
                    bot_version=settings.bot_version
                )
                session.add(config)
            else:
                config.management_category_id = category.id
                config.management_channel_id = channel.id
                config.management_message_id = message.id
                config.setup_complete = True
                config.bot_version = settings.bot_version

            await session.commit()

        logger.info("guild.setup.completed", guild_id=guild.id)

    async def _get_or_create_category(self, guild: discord.Guild) -> discord.CategoryChannel:
        # Check DB first
        async with get_db_session() as session:
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == guild.id)
            )
            config = result.scalar_one_or_none()
            if config and config.management_category_id:
                existing = guild.get_channel(config.management_category_id)
                if existing:
                    return existing

        # Create new category
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
        }
        for member in guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True)

        category = await guild.create_category_channel(
            self.management_category_name,
            overwrites=overwrites,
            reason="Team Management Bot - Management Category"
        )
        return category

    async def _get_or_create_channel(self, guild: discord.Guild, category: discord.CategoryChannel) -> discord.TextChannel:
        async with get_db_session() as session:
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == guild.id)
            )
            config = result.scalar_one_or_none()
            if config and config.management_channel_id:
                existing = guild.get_channel(config.management_channel_id)
                if existing and isinstance(existing, discord.TextChannel):
                    return existing

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for member in guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            self.management_channel_name,
            category=category,
            overwrites=overwrites,
            reason="Team Management Bot - Management Channel"
        )
        return channel

    async def _get_or_create_panel(self, channel: discord.TextChannel) -> discord.Message:
        from bot.views.management_panel import ManagementPanelView
        from bot.embeds.base import EmbedBuilder

        # Try to find existing message via DB
        async with get_db_session() as session:
            result = await session.execute(
                select(GuildConfiguration).where(GuildConfiguration.guild_id == channel.guild.id)
            )
            config = result.scalar_one_or_none()
            if config and config.management_message_id:
                try:
                    msg = await channel.fetch_message(config.management_message_id)
                    return msg
                except discord.NotFound:
                    pass

        embed = EmbedBuilder.management(
            "Team Management",
            "Professional tournament team management system.\n\n"
            "Use the buttons below to manage teams."
        )
        view = ManagementPanelView()
        message = await channel.send(embed=embed, view=view)
        return message
