from __future__ import annotations

import io
from datetime import datetime, timedelta

import discord
from discord import ui
from sqlalchemy import func, select

from bot.embeds.base import EmbedBuilder
from bot.services.giveaway_service import GiveawayService
from bot.services.leaderboard_card import CARD_FILENAME, render_top_five_card
from bot.services.permission_service import PermissionService
from bot.services.pulse_service import PulseService, band_for_level
from database.session import get_db_session
from models.models import (
    Giveaway,
    GiveawayStatus,
    PulseMember,
    PulsePacing,
    PulseSettings,
    XPSource,
)


def _state(value: bool) -> str:
    return "✅ Active" if value else "⏸ Paused"


async def community_systems_embed(guild: discord.Guild, bot=None) -> discord.Embed:
    pulse = await PulseService(bot).get_or_create_settings(guild)
    async with get_db_session() as session:
        tracked = (
            await session.execute(
                select(func.count(PulseMember.id)).where(PulseMember.guild_id == guild.id)
            )
        ).scalar_one()
        live = (
            await session.execute(
                select(func.count(Giveaway.id)).where(
                    Giveaway.guild_id == guild.id,
                    Giveaway.status.in_([GiveawayStatus.LIVE, GiveawayStatus.PAUSED]),
                )
            )
        ).scalar_one()
        scheduled = (
            await session.execute(
                select(func.count(Giveaway.id)).where(
                    Giveaway.guild_id == guild.id,
                    Giveaway.status == GiveawayStatus.SCHEDULED,
                )
            )
        ).scalar_one()
    leaderboard = (
        f"<#{pulse.leaderboard_channel_id}>"
        if pulse.leaderboard_channel_id else "Not configured"
    )
    description = (
        f"**Guild Pulse**       {_state(pulse.enabled)} · {tracked} members tracked\n"
        f"**Pacing**            {pulse.pacing.value.title()}\n"
        f"**Leaderboard**       {leaderboard}\n"
        f"**Giveaways**         ✅ {live} live · {scheduled} scheduled\n\n"
        "Choose a system below. Administrator controls are private."
    )
    return EmbedBuilder.info("✦ Community Systems", description)


class CommunitySystemsView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)

    @ui.button(label="◈ Guild Pulse", style=discord.ButtonStyle.primary)
    async def pulse(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await pulse_admin_embed(self.guild, self.bot),
            view=PulseAdminView(self.bot, self.guild),
        )

    @ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary)
    async def giveaways(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await giveaway_admin_embed(self.guild),
            view=GiveawayAdminView(self.bot, self.guild),
        )

    @ui.button(label="📊 Activity & Health", style=discord.ButtonStyle.secondary, row=1)
    async def health(self, interaction: discord.Interaction, button: ui.Button):
        from bot.services.health_service import HealthService

        health = await HealthService.full_health_check(self.bot)
        await interaction.response.edit_message(
            embed=EmbedBuilder.info(
                "📊 Activity & Health",
                "\n".join(f"**{key.replace('_', ' ').title()}:** {value}" for key, value in health.items()),
            ),
            view=self,
        )


async def pulse_admin_embed(guild: discord.Guild, bot=None) -> discord.Embed:
    settings = await PulseService(bot).get_or_create_settings(guild)
    source_values = settings.enabled_sources or []
    sources = " ".join(
        f"{'✅' if key in source_values else '⏸'} {key.title()}"
        for key in ("message", "voice", "reaction", "event")
    )
    return EmbedBuilder.info(
        "◈ Guild Pulse",
        f"**Status:** {_state(settings.enabled)}\n"
        f"**Pace:** {settings.pacing.value.title()}\n"
        f"**Tracked members:** {await _pulse_count(guild.id)}\n"
        f"**Max level:** {settings.max_level}\n\n"
        f"**XP sources**\n{sources}\n\n"
        "Use **My Pulse** or **Leaderboard** to preview the member experience.",
    )


async def _pulse_count(guild_id: int) -> int:
    async with get_db_session() as session:
        return (
            await session.execute(
                select(func.count(PulseMember.id)).where(PulseMember.guild_id == guild_id)
            )
        ).scalar_one()


class PulseAdminView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)

    @ui.button(label="▶ Enable / Pause XP", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: ui.Button):
        settings = await PulseService(self.bot).get_or_create_settings(self.guild)
        await PulseService(self.bot).configure(
            self.guild, interaction.user, enabled=not settings.enabled
        )
        await interaction.response.edit_message(
            embed=await pulse_admin_embed(self.guild, self.bot), view=self
        )

    @ui.button(label="⚙ Configure Sources", style=discord.ButtonStyle.secondary)
    async def configure(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(PulseSourceModal(self))

    @ui.button(label="⏱ Change Pace", style=discord.ButtonStyle.secondary, row=1)
    async def pace(self, interaction: discord.Interaction, button: ui.Button):
        settings = await PulseService(self.bot).get_or_create_settings(self.guild)
        order = [PulsePacing.RELAXED, PulsePacing.BALANCED, PulsePacing.AMBITIOUS]
        next_pace = order[(order.index(settings.pacing) + 1) % len(order)]
        await PulseService(self.bot).configure(
            self.guild, interaction.user, pacing=next_pace
        )
        await interaction.response.edit_message(
            embed=await pulse_admin_embed(self.guild, self.bot), view=self
        )

    @ui.button(label="📈 My Pulse", style=discord.ButtonStyle.primary, row=1)
    async def my_pulse(self, interaction: discord.Interaction, button: ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.send_message(
            embed=await pulse_profile_embed(self.guild, interaction.user, self.bot),
            view=PulseMemberView(self.bot, self.guild),
            ephemeral=True,
        )

    @ui.button(label="🎖 Create / Sync Band Roles", style=discord.ButtonStyle.secondary, row=2)
    async def band_roles(self, interaction: discord.Interaction, button: ui.Button):
        created, failed = await PulseService(self.bot).ensure_band_roles(
            self.guild, interaction.user.id
        )
        await interaction.response.edit_message(
            embed=EmbedBuilder.success(
                "Band Roles Synchronized",
                f"Created: **{created}**\n"
                f"Synchronization warnings: **{failed}**\n\n"
                "Only bot-owned Guild Pulse roles were changed.",
            ),
            view=self,
        )

    @ui.button(label="🧾 Manual XP Award", style=discord.ButtonStyle.secondary, row=3)
    async def manual_award(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ManualXPAwardModal(self))

    @ui.button(label="📊 Publish Leaderboard", style=discord.ButtonStyle.secondary, row=3)
    async def publish_leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "Choose Leaderboard Channel", "Select the public channel for the in-place leaderboard."
            ),
            view=PulseLeaderboardChannelView(self),
            ephemeral=True,
        )

    @ui.button(label="🏆 Leaderboard", style=discord.ButtonStyle.primary, row=2)
    async def leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=(payload := await leaderboard_payload(
                self.guild, self.bot, interaction.user.id
            ))[0],
            file=payload[1],
            view=PulseMemberView(self.bot, self.guild),
            ephemeral=True,
        )

    @ui.button(label="↩ Community Systems", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await community_systems_embed(self.guild, self.bot),
            view=CommunitySystemsView(self.bot, self.guild),
        )


class PulseSourceModal(ui.Modal, title="Configure Guild Pulse Sources"):
    def __init__(self, parent):
        super().__init__()
        self.parent_view = parent
        self.source_input = ui.TextInput(
            label="Sources",
            placeholder="message, voice, reaction, event",
            default="message",
            required=True,
            max_length=100,
        )
        self.add_item(self.source_input)

    async def on_submit(self, interaction: discord.Interaction):
        values = [item.strip().lower() for item in self.source_input.value.split(",") if item.strip()]
        allowed = {"message", "voice", "reaction", "event"}
        if not values or not set(values).issubset(allowed):
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid Sources", "Use one or more of: message, voice, reaction, event."
                ),
                ephemeral=True,
            )
            return
        await PulseService(self.parent_view.bot).configure(
            self.parent_view.guild,
            interaction.user,
            sources=list(dict.fromkeys(values)),
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Pulse Updated", f"Enabled sources: {', '.join(values)}."),
            ephemeral=True,
        )


class ManualXPAwardModal(ui.Modal, title="Manual Pulse XP Adjustment"):
    def __init__(self, parent):
        super().__init__()
        self.parent_view = parent
        self.member_input = ui.TextInput(
            label="Member ID or mention", required=True, max_length=30
        )
        self.amount_input = ui.TextInput(
            label="XP amount (negative allowed)", required=True, max_length=10
        )
        self.reason_input = ui.TextInput(
            label="Required reason", style=discord.TextStyle.paragraph,
            required=True, max_length=500
        )
        for item in (self.member_input, self.amount_input, self.reason_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        raw_member = self.member_input.value.strip().replace("<@", "").replace("!", "").replace(">", "")
        try:
            member = self.parent_view.guild.get_member(int(raw_member))
            amount = int(self.amount_input.value)
        except (ValueError, TypeError):
            member = None
            amount = 0
        if not member or amount == 0:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid Adjustment", "Use a valid member ID/mention and a non-zero XP amount."
                ),
                ephemeral=True,
            )
            return
        ok, message, _ = await PulseService(self.parent_view.bot).award_xp(
            self.parent_view.guild,
            member,
            amount,
            XPSource.MANUAL,
            f"manual:{self.parent_view.guild.id}:{member.id}:{interaction.id}",
            reason=self.reason_input.value,
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("XP Adjustment Recorded", message)
            if ok else EmbedBuilder.warning("XP Adjustment Skipped", message),
            ephemeral=True,
        )


class PulseLeaderboardChannelView(ui.View):
    def __init__(self, parent):
        super().__init__(timeout=180)
        self.parent_view = parent
        self.add_item(PulseLeaderboardChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)


class PulseLeaderboardChannelSelect(ui.ChannelSelect):
    def __init__(self, parent):
        self.parent_view = parent
        super().__init__(
            placeholder="Select leaderboard channel...",
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        service = PulseService(self.parent_view.parent_view.bot)
        await service.set_leaderboard_channel(
            self.parent_view.parent_view.guild, interaction.user, channel.id
        )
        await service.refresh_leaderboard(self.parent_view.parent_view.guild)
        await interaction.response.send_message(
            embed=EmbedBuilder.success(
                "Leaderboard Published", f"The leaderboard is active in {channel.mention}."
            ),
            ephemeral=True,
        )


async def pulse_profile_embed(
    guild: discord.Guild, member: discord.Member, bot=None
) -> discord.Embed:
    data = await PulseService(bot).profile(guild, member)
    filled = round((data["current"] / max(1, data["needed"])) * 16)
    bar = "▰" * min(16, filled) + "░" * max(0, 16 - filled)
    return EmbedBuilder.info(
        f"◈ {member.display_name}'s Pulse",
        f"**Level {data['level']} · {data['band'].get('name', 'Signal')}**\n\n"
        f"{bar}  **{data['current']} / {data['needed']} XP**\n\n"
        f"**Rank:** #{data['rank']}\n"
        f"**Last 7 days:** {data['seven_days']} XP\n"
        f"**Total XP:** {data['total']}\n\n"
        f"**Next milestone:** Level {data['level'] + 1}",
    )


async def leaderboard_payload(
    guild: discord.Guild, bot=None, viewer_id: int | None = None
) -> tuple[discord.Embed, discord.File]:
    service = PulseService(bot)
    rows = await service.leaderboard(guild, limit=5)
    settings = await service.get_or_create_settings(guild)
    brand = settings.brand_config or {}
    accent = int(brand.get("color", 0xD6A84F))
    viewer_profile = None
    if viewer_id:
        viewer = guild.get_member(viewer_id)
        if viewer:
            viewer_profile = await service.profile(guild, viewer)
    embed = discord.Embed(
        title="✦ PULSE ORBIT  ·  TOP FIVE",
        description=(
            "**GUILD PULSE · SIGNAL INDEX**\n"
            "A visual map of the five signals moving this server forward."
        ),
        color=accent,
        timestamp=datetime.utcnow(),
    )
    author = {"name": f"{settings.display_name or 'Guild Pulse'}  ·  LEADERBOARD"}
    if guild.icon:
        author["icon_url"] = guild.icon.url
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_author(**author)

    card = await render_top_five_card(
        guild, rows, settings, viewer_id, viewer_profile=viewer_profile
    )
    embed.set_image(url=f"attachment://{CARD_FILENAME}")
    embed.set_footer(
        text="Guild Pulse  •  Top five updated live  •  Tap My Pulse for your path"
    )
    return embed, discord.File(io.BytesIO(card), filename=CARD_FILENAME)


async def leaderboard_embed(
    guild: discord.Guild, bot=None, viewer_id: int | None = None
) -> discord.Embed:
    """Compatibility wrapper for callers that only need the embed metadata."""
    return (await leaderboard_payload(guild, bot, viewer_id))[0]


class PulseMemberView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild

    @ui.button(label="📈 My Pulse", style=discord.ButtonStyle.primary)
    async def profile(self, interaction: discord.Interaction, button: ui.Button):
        if isinstance(interaction.user, discord.Member):
            await interaction.response.edit_message(
                embed=await pulse_profile_embed(self.guild, interaction.user, self.bot), view=self
            )

    @ui.button(label="🏆 Leaderboard", style=discord.ButtonStyle.secondary)
    async def leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        payload = await leaderboard_payload(
            self.guild, self.bot, interaction.user.id
        )
        await interaction.response.edit_message(
            embed=payload[0],
            attachments=[payload[1]],
            view=self,
        )

    @ui.button(label="🕒 History", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "🕒 Pulse History",
                "Recent XP history is available privately. Ledger details are not publicly exposed.",
            ),
            ephemeral=True,
        )


async def giveaway_admin_embed(guild: discord.Guild) -> discord.Embed:
    async with get_db_session() as session:
        counts = {}
        for status in (GiveawayStatus.LIVE, GiveawayStatus.SCHEDULED, GiveawayStatus.COMPLETED):
            counts[status.value] = (
                await session.execute(
                    select(func.count(Giveaway.id)).where(
                        Giveaway.guild_id == guild.id, Giveaway.status == status
                    )
                )
            ).scalar_one()
    return EmbedBuilder.info(
        "🎁 Giveaways",
        f"**Live:** {counts['live']}\n**Scheduled:** {counts['scheduled']}\n"
        f"**Completed:** {counts['completed']}\n\n"
        "The organizer remains responsible for supplying and fulfilling every prize.",
    )


class GiveawayAdminView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)

    @ui.button(label="🎁 Create Giveaway", style=discord.ButtonStyle.success)
    async def create(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Choose Giveaway Channel", "Select the public entry channel."),
            view=GiveawayChannelView(self.bot, self.guild),
            ephemeral=True,
        )

    @ui.button(label="📋 Live & Scheduled", style=discord.ButtonStyle.primary)
    async def list_items(self, interaction: discord.Interaction, button: ui.Button):
        async with get_db_session() as session:
            items = list(
                (
                    await session.execute(
                        select(Giveaway).where(
                            Giveaway.guild_id == self.guild.id,
                            Giveaway.status.in_(
                                [GiveawayStatus.LIVE, GiveawayStatus.SCHEDULED]
                            ),
                        ).order_by(Giveaway.end_at.asc()).limit(10)
                    )
                ).scalars().all()
            )
        description = "\n".join(
            f"• **{item.title}** · {item.status.value} · <t:{int(item.end_at.timestamp())}:R>"
            for item in items
        ) or "No active giveaways."
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Giveaway Operations", description), ephemeral=True
        )

    @ui.button(label="⏸ Pause / Resume", style=discord.ButtonStyle.secondary, row=1)
    async def pause_resume(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "Giveaway ID Required",
                "Use the giveaway ID from the live list to pause or resume it.",
            ),
            view=GiveawayActionView(self.bot, self.guild, "pause"),
            ephemeral=True,
        )

    @ui.button(label="⏹ End Now", style=discord.ButtonStyle.secondary, row=1)
    async def end_now(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            GiveawayActionModal(self.bot, self.guild, "end")
        )

    @ui.button(label="🛑 Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            GiveawayActionModal(self.bot, self.guild, "cancel")
        )

    @ui.button(label="🔁 Reroll", style=discord.ButtonStyle.secondary, row=2)
    async def reroll(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            GiveawayActionModal(self.bot, self.guild, "reroll")
        )

    @ui.button(label="↩ Community Systems", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await community_systems_embed(self.guild, self.bot),
            view=CommunitySystemsView(self.bot, self.guild),
        )


class GiveawayChannelView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.add_item(GiveawayChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)


class GiveawayChannelSelect(ui.ChannelSelect):
    def __init__(self, parent):
        self.parent_view = parent
        super().__init__(
            placeholder="Select entry channel...",
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            GiveawayCreateModal(self.parent_view, self.values[0].id)
        )


class GiveawayCreateModal(ui.Modal, title="Create Giveaway"):
    def __init__(self, parent, channel_id: int):
        super().__init__()
        self.parent_view = parent
        self.channel_id = channel_id
        self.title_input = ui.TextInput(label="Prize title", max_length=256, required=True)
        self.prize_input = ui.TextInput(
            label="Prize description", style=discord.TextStyle.paragraph,
            max_length=1000, required=True,
        )
        self.duration_input = ui.TextInput(
            label="Start delay, duration (minutes)", default="0,60", max_length=16, required=True
        )
        self.winners_input = ui.TextInput(
            label="Number of winners", default="1", max_length=3, required=True
        )
        self.ack_input = ui.TextInput(
            label="Type ACK to confirm organizer fulfillment", max_length=3, required=True
        )
        for item in (
            self.title_input, self.prize_input, self.duration_input,
            self.winners_input, self.ack_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            schedule_values = [int(item.strip()) for item in self.duration_input.value.split(",")]
            if len(schedule_values) != 2:
                raise ValueError
            start_delay, duration = schedule_values
            winners = int(self.winners_input.value)
        except ValueError:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Schedule", "Duration and winners must be numbers."),
                ephemeral=True,
            )
            return
        ok, message, giveaway_id = await GiveawayService(self.parent_view.bot).create(
            self.parent_view.guild, interaction.user,
            channel_id=self.channel_id,
            title=self.title_input.value,
            prize_description=self.prize_input.value,
            start_at=datetime.utcnow() + timedelta(minutes=max(0, start_delay)),
            end_at=datetime.utcnow() + timedelta(minutes=max(1, start_delay + duration)),
            winner_count=winners,
            acknowledge_prize_responsibility=self.ack_input.value.strip().upper() == "ACK",
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Giveaway Created", message)
            if ok else EmbedBuilder.error("Giveaway Not Created", message),
            ephemeral=True,
        )


class GiveawayActionView(ui.View):
    def __init__(self, bot, guild: discord.Guild, action: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.action = action
        self.add_item(GiveawayIdSelect(self))


class GiveawayIdSelect(ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        super().__init__(
            placeholder="Select a giveaway...",
            options=[discord.SelectOption(label="Enter the giveaway ID in the modal", value="modal")],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            GiveawayActionModal(
                self.parent_view.bot,
                self.parent_view.guild,
                self.parent_view.action,
            )
        )


class GiveawayActionModal(ui.Modal):
    def __init__(self, bot, guild: discord.Guild, action: str):
        super().__init__(title=f"Giveaway {action.title()}")
        self.bot = bot
        self.guild = guild
        self.action = action
        self.id_input = ui.TextInput(label="Giveaway ID", required=True, max_length=20)
        self.reason_input = ui.TextInput(
            label="Reason (required for cancel/reroll)",
            required=action in {"cancel", "reroll"},
            max_length=500,
        )
        self.add_item(self.id_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            giveaway_id = int(self.id_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Giveaway ID", "Enter the numeric giveaway ID."),
                ephemeral=True,
            )
            return
        service = GiveawayService(self.bot)
        if self.action == "pause":
            ok, message = await service.pause_or_resume(
                self.guild, giveaway_id, interaction.user.id
            )
        elif self.action == "end":
            ok, message = await service.end(
                self.guild, giveaway_id, interaction.user.id, "administrator_end"
            )
        elif self.action == "cancel":
            ok, message = await service.cancel(
                self.guild, giveaway_id, interaction.user.id, self.reason_input.value
            )
        else:
            ok, message = await service.reroll(
                self.guild, giveaway_id, interaction.user.id, self.reason_input.value
            )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Giveaway Updated", message)
            if ok else EmbedBuilder.error("Giveaway Action Failed", message),
            ephemeral=True,
        )