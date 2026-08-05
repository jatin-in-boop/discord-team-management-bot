from __future__ import annotations

import discord
from discord import ui
from sqlalchemy import select

from bot.embeds.base import EmbedBuilder
from bot.services.community_service import CommunityService
from bot.services.invite_tracker_service import InviteTrackerService
from bot.services.permission_service import PermissionService
from database.session import get_db_session
from models.models import CommunitySettings


async def _settings(guild_id: int) -> CommunitySettings | None:
    async with get_db_session() as session:
        return (
            await session.execute(
                select(CommunitySettings).where(CommunitySettings.guild_id == guild_id)
            )
        ).scalar_one_or_none()


def _channel(guild: discord.Guild, channel_id: int | None) -> str:
    return guild.get_channel(channel_id).mention if channel_id and guild.get_channel(channel_id) else "Not configured"


async def logging_embed(guild: discord.Guild) -> discord.Embed:
    settings = await CommunityService.get_or_create_settings(guild)
    return EmbedBuilder.info(
        "🧭 Invite Tracker & Server Logs",
        f"**Invite Tracker:** {'✅ Active' if settings.invite_tracker_enabled else '⏸ Disabled'} · "
        f"{_channel(guild, settings.invite_tracker_channel_id)}\n"
        f"**Server Logs:** {'✅ Active' if settings.audit_logging_enabled else '⏸ Disabled'} · "
        f"{_channel(guild, settings.audit_log_channel_id)}\n\n"
        "Choose a destination below. The bot never creates a channel automatically.\n"
        "Server logs group nearby events into compact summaries instead of sending one message per action.\n"
        "Use **Log Detail Settings** to opt into message, voice, or bot-automation events.",
    )


class CommunityLoggingView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.add_item(LoggingChannelSelect(self, "invite_tracker", "Invite Tracker channel"))
        self.add_item(LoggingChannelSelect(self, "audit_logging", "Server Logs channel"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)

    @ui.button(label="🔄 Refresh Invite Cache", style=discord.ButtonStyle.primary, row=2)
    async def refresh_invites(self, interaction: discord.Interaction, button: ui.Button):
        count = await InviteTrackerService(interaction.client).sync_guild(self.guild)
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Invite Cache Refreshed", f"Tracked {count} invite(s)."),
            ephemeral=True,
        )

    @ui.button(label="⚙ Log Detail Settings", style=discord.ButtonStyle.primary, row=2)
    async def log_details(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.log_detail_settings import LogDetailModal

        settings = await CommunityService.get_or_create_settings(self.guild)
        await interaction.response.send_modal(
            LogDetailModal(self, settings.audit_log_config or {})
        )

    @ui.button(label="⏸ Disable Invite Tracker", style=discord.ButtonStyle.secondary, row=2)
    async def disable_invites(self, interaction: discord.Interaction, button: ui.Button):
        await self._disable(interaction, "invite_tracker")

    @ui.button(label="⏸ Disable Server Logs", style=discord.ButtonStyle.secondary, row=2)
    async def disable_logs(self, interaction: discord.Interaction, button: ui.Button):
        await self._disable(interaction, "audit_logging")

    @ui.button(label="↩ Community Systems", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.community_systems import CommunitySystemsView, community_systems_embed
        await interaction.response.edit_message(
            embed=await community_systems_embed(self.guild, self.bot),
            view=CommunitySystemsView(self.bot, self.guild),
        )

    async def _disable(self, interaction: discord.Interaction, feature: str):
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == self.guild.id)
                )
            ).scalar_one_or_none()
            if settings:
                setattr(settings, f"{feature}_enabled", False)
        await interaction.response.edit_message(
            embed=await logging_embed(self.guild),
            view=self,
        )

    async def render_embed(self) -> discord.Embed:
        return await logging_embed(self.guild)


class LoggingChannelSelect(ui.ChannelSelect):
    def __init__(self, parent: CommunityLoggingView, feature: str, placeholder: str):
        self.parent_view = parent
        self.feature = feature
        super().__init__(
            placeholder=placeholder,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0 if feature == "invite_tracker" else 1,
        )

    async def callback(self, interaction: discord.Interaction):
        ok, message = await CommunityService.set_channel_feature(
            self.parent_view.guild,
            interaction.user,
            self.feature,
            self.values[0].id,
        )
        await interaction.response.edit_message(
            embed=(await logging_embed(self.parent_view.guild))
            if ok else EmbedBuilder.error("Channel Not Saved", message),
            view=self.parent_view,
        )