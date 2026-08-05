from __future__ import annotations

from typing import Any

import discord
from discord import ui
from sqlalchemy import select, func

from app_logging.logger import get_logger
from bot.embeds.base import EmbedBuilder
from bot.services.community_service import (
    CommunityService,
    GOODBYE_DEFAULT,
    WELCOME_DEFAULT,
)
from bot.services.permission_service import PermissionService
from database.session import get_db_session
from models.models import CommunitySettings, ReactionRoleOption, ReactionRolePanel

logger = get_logger(__name__)


async def _settings(guild_id: int) -> CommunitySettings | None:
    async with get_db_session() as session:
        return (
            await session.execute(
                select(CommunitySettings).where(CommunitySettings.guild_id == guild_id)
            )
        ).scalar_one_or_none()


def _channel_label(guild: discord.Guild, channel_id: int | None) -> str:
    channel = guild.get_channel(channel_id) if channel_id else None
    return channel.mention if channel else "Not configured"


async def community_status_embed(guild: discord.Guild) -> discord.Embed:
    settings = await CommunityService.get_or_create_settings(guild)
    async with get_db_session() as session:
        panel_count = (
            await session.execute(
                select(func.count(ReactionRolePanel.id)).where(ReactionRolePanel.guild_id == guild.id)
            )
        ).scalar_one()
        option_count = (
            await session.execute(
                select(func.count(ReactionRoleOption.id))
                .join(ReactionRolePanel, ReactionRoleOption.panel_id == ReactionRolePanel.id)
                .where(ReactionRolePanel.guild_id == guild.id)
            )
        ).scalar_one()
    welcome_state = "✅ Enabled" if settings.welcome_enabled else "⏸ Disabled"
    goodbye_state = "✅ Enabled" if settings.goodbye_enabled else "⏸ Disabled"
    reaction_state = "✅ Active" if panel_count else "⏸ No panels"
    description = (
        f"**Welcome**      {welcome_state} · {_channel_label(guild, settings.welcome_channel_id)}\n"
        f"**Goodbye**      {goodbye_state} · {_channel_label(guild, settings.goodbye_channel_id)}\n"
        f"**Reaction**     {reaction_state} · {panel_count} panel(s) · {option_count} role option(s)\n\n"
        "Choose a feature below. All administrator controls are private."
    )
    if settings.welcome_status or settings.goodbye_status:
        description += "\n\n⚠️ **Needs attention**"
        if settings.welcome_status:
            description += f"\nWelcome: {settings.welcome_status}"
        if settings.goodbye_status:
            description += f"\nGoodbye: {settings.goodbye_status}"
    return EmbedBuilder.info("✨ Community Features", description)


class CommunityFeaturesView(ui.View):
    def __init__(self, bot=None):
        super().__init__(timeout=300)
        self.bot = bot

    @ui.button(label="👋 Welcome Message", style=discord.ButtonStyle.primary)
    async def welcome(self, interaction: discord.Interaction, button: ui.Button):
        await _show_message_settings(interaction, "welcome")

    @ui.button(label="🚪 Goodbye Message", style=discord.ButtonStyle.primary)
    async def goodbye(self, interaction: discord.Interaction, button: ui.Button):
        await _show_message_settings(interaction, "goodbye")

    @ui.button(label="🎭 Reaction Roles", style=discord.ButtonStyle.secondary)
    async def reaction_roles(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.reaction_roles import ReactionRoleAdminView

        if not interaction.guild:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Server Only", "This feature must be used inside a server."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=await ReactionRoleAdminView.status_embed(interaction.guild),
            view=ReactionRoleAdminView(interaction.client, interaction.guild, interaction.user),
            ephemeral=True,
        )

    @ui.button(label="↩ Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.management_panel import ManagementPanelView

        if not interaction.guild:
            return
        await interaction.response.edit_message(
            embed=await community_status_embed(interaction.guild),
            view=ManagementPanelView(interaction.client),
        )


class MessageSettingsView(ui.View):
    def __init__(self, guild: discord.Guild, kind: str):
        super().__init__(timeout=300)
        self.guild = guild
        self.kind = kind
        self.add_item(MessageChannelSelect(kind))

    @ui.button(label="✏️ Edit Message", style=discord.ButtonStyle.primary)
    async def edit_message(self, interaction: discord.Interaction, button: ui.Button):
        settings = await CommunityService.get_or_create_settings(self.guild)
        config = (
            settings.welcome_message_config
            if self.kind == "welcome"
            else settings.goodbye_message_config
        )
        await interaction.response.send_modal(
            MessageConfigModal(self.guild, interaction.user, self.kind, config or {})
        )

    @ui.button(label="👁 Preview", style=discord.ButtonStyle.secondary)
    async def preview(self, interaction: discord.Interaction, button: ui.Button):
        settings = await CommunityService.get_or_create_settings(self.guild)
        config = (
            settings.welcome_message_config
            if self.kind == "welcome"
            else settings.goodbye_message_config
        )
        member = interaction.user
        preview_content = (
            f"{member.mention}  **entry confirmed**\n"
            f"`{self.guild.name.upper()} // ARRIVAL PROTOCOL COMPLETE`"
            if self.kind == "welcome"
            else f"**{member.display_name}**  has left the room."
        )
        from bot.services.community_service import build_config_embed
        from bot.services.community_service import _banner_file

        await interaction.response.send_message(
            content=preview_content,
            embed=build_config_embed(config, self.guild, member, self.kind, test=True),
            file=_banner_file(config, self.kind),
            allowed_mentions=discord.AllowedMentions(
                users=True, roles=False, everyone=False
            ),
            ephemeral=True,
        )

    @ui.button(label="🔘 Enable / Disable", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: ui.Button):
        settings = await CommunityService.get_or_create_settings(self.guild)
        enabled = settings.welcome_enabled if self.kind == "welcome" else settings.goodbye_enabled
        ok, message = await CommunityService.set_enabled(
            self.guild, interaction.user, self.kind, not enabled
        )
        await interaction.response.edit_message(
            embed=EmbedBuilder.success(f"{self.kind.title()} Message", message)
            if ok
            else EmbedBuilder.error(f"{self.kind.title()} Message", message),
            view=MessageSettingsView(self.guild, self.kind),
        )

    @ui.button(label="🧪 Send Test", style=discord.ButtonStyle.secondary)
    async def test(self, interaction: discord.Interaction, button: ui.Button):
        ok, message = await CommunityService.send_configured_message(
            self.guild, interaction.user, self.kind, test=True
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Test Sent", message)
            if ok
            else EmbedBuilder.error("Test Failed", message),
            ephemeral=True,
        )

    @ui.button(label="🗑 Reset", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, interaction: discord.Interaction, button: ui.Button):
        await CommunityService.reset(self.guild, interaction.user, self.kind)
        await interaction.response.edit_message(
            embed=EmbedBuilder.success(
                f"{self.kind.title()} Reset",
                "The feature is disabled and its message settings were restored to defaults.",
            ),
            view=MessageSettingsView(self.guild, self.kind),
        )

    @ui.button(label="↩ Community Features", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await community_status_embed(self.guild),
            view=CommunityFeaturesView(interaction.client),
        )


class MessageChannelSelect(ui.ChannelSelect):
    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(
            placeholder="Choose the destination channel...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        settings = await CommunityService.get_or_create_settings(interaction.guild)
        async with get_db_session() as session:
            db_settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == interaction.guild.id)
                )
            ).scalar_one()
            if self.kind == "welcome":
                db_settings.welcome_channel_id = channel.id
            else:
                db_settings.goodbye_channel_id = channel.id
            db_settings.updated_by = interaction.user.id
            await session.commit()
        await interaction.response.send_message(
            embed=EmbedBuilder.success(
                "Destination Saved",
                f"{self.kind.title()} messages will use {channel.mention}.",
            ),
            ephemeral=True,
        )


async def _show_message_settings(interaction: discord.Interaction, kind: str):
    if not interaction.guild:
        await interaction.response.send_message(
            embed=EmbedBuilder.error("Server Only", "This feature must be used inside a server."),
            ephemeral=True,
        )
        return
    settings = await CommunityService.get_or_create_settings(interaction.guild)
    enabled = settings.welcome_enabled if kind == "welcome" else settings.goodbye_enabled
    channel_id = settings.welcome_channel_id if kind == "welcome" else settings.goodbye_channel_id
    config = settings.welcome_message_config if kind == "welcome" else settings.goodbye_message_config
    status = f"✅ Enabled" if enabled else "⏸ Disabled"
    details = (
        f"Status: **{status}**\n"
        f"Destination: {_channel_label(interaction.guild, channel_id)}\n"
        f"Style: **{config.get('style', 'plain')}**\n\n"
        "Select a channel, edit the message, preview it privately, or send a test."
    )
    await interaction.response.send_message(
        embed=EmbedBuilder.info(f"{'👋' if kind == 'welcome' else '🚪'} {kind.title()} Message", details),
        view=MessageSettingsView(interaction.guild, kind),
        ephemeral=True,
    )


class MessageConfigModal(ui.Modal):
    def __init__(self, guild: discord.Guild, executor: discord.Member, kind: str, config: dict[str, Any]):
        super().__init__(title=f"Edit {kind.title()} Message")
        self.guild = guild
        self.executor = executor
        self.kind = kind
        self.title_input = ui.TextInput(
            label="Title (optional)",
            default=config.get("title", ""),
            required=False,
            max_length=256,
        )
        self.description_input = ui.TextInput(
            label="Message",
            default=config.get("description", ""),
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        self.style_input = ui.TextInput(
            label="Style: plain or embed",
            default=config.get("style", "plain"),
            required=True,
            max_length=10,
        )
        self.footer_input = ui.TextInput(
            label="Footer (optional)",
            default=config.get("footer", ""),
            required=False,
            max_length=2048,
        )
        self.banner_input = ui.TextInput(
            label="Banner URL (blank = default)",
            default=config.get("banner_url", ""),
            required=False,
            max_length=512,
        )
        for item in (
            self.title_input,
            self.description_input,
            self.style_input,
            self.footer_input,
            self.banner_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        settings = await CommunityService.get_or_create_settings(self.guild)
        channel_id = settings.welcome_channel_id if self.kind == "welcome" else settings.goodbye_channel_id
        if not channel_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Choose a Channel First",
                    "Select a destination channel before saving this message.",
                ),
                ephemeral=True,
            )
            return
        style = self.style_input.value.strip().lower()
        if style not in {"plain", "embed"}:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Style", "Style must be `plain` or `embed`."),
                ephemeral=True,
            )
            return
        config = {
            "style": style,
            "title": self.title_input.value.strip(),
            "description": self.description_input.value.strip(),
            "footer": self.footer_input.value.strip(),
            "thumbnail": self.kind == "welcome",
            "mention": self.kind == "welcome",
            "banner_url": self.banner_input.value.strip(),
        }
        ok, message = await CommunityService.save_message_config(
            self.guild, self.executor, self.kind, channel_id, config
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Saved", message)
            if ok
            else EmbedBuilder.error("Could Not Save", message),
            ephemeral=True,
        )