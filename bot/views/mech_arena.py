from __future__ import annotations

import discord
from discord import ui

from app_logging.logger import get_logger
from bot.embeds.base import EmbedBuilder
from bot.services.mech_arena_service import MechArenaService, groq_broker
from bot.services.permission_service import PermissionService

logger = get_logger(__name__)


def _calculation_text(result: dict) -> str:
    total = result["total"]
    lines = [
        f"**{result['item'].get('list') or result['item'].get('name') or result['item'].get('mod_label')}**",
        f"Type: **{result['item_kind'].title()}** · level {result['from_level']} → "
        f"{result['to_level']}" + (f" · {result['star']}★" if "star" in result else ""),
    ]
    labels = {
        "credits": "Credits",
        "acoins": "A-Coins",
        "blueprints": "Blueprints",
        "marks": "Marks",
        "xp": "XP",
        "basic_mod_parts": "Basic mod parts",
        "elite_mod_parts": "Elite mod parts",
        "power": "Power",
    }
    lines.extend(f"{labels[key]}: **{value:,}**" for key, value in total.items())
    lines.append(f"Source snapshot: `{result['source'][:19].replace('T', ' ')} UTC`")
    return "\n".join(lines)


def _format_status(status: dict) -> str:
    lines = []
    for source in ("google_sheet", "calculator"):
        item = status.get(source)
        if not item:
            lines.append(f"**{source.replace('_', ' ').title()}:** Not synced")
            continue
        lines.append(
            f"**{source.replace('_', ' ').title()}:** "
            f"{item['fetched_at'].replace('T', ' ')[:19]} UTC · `{item['hash']}`"
        )
    lines.append(f"**Groq keys configured:** {status.get('groq_keys_configured', 0)}")
    lines.append(f"**Website polling:** every {status.get('poll_seconds', 900)} seconds")
    lines.append(f"**Maximum answer age:** {status.get('max_stale_seconds', 86400)} seconds")
    return "\n".join(lines)


async def mech_arena_admin_embed(guild: discord.Guild | None = None) -> discord.Embed:
    guild_settings = (
        await MechArenaService.ensure_guild_settings(guild.id) if guild else None
    )
    question_channel = (
        f"<#{guild_settings.question_channel_id}>"
        if guild_settings and guild_settings.question_channel_id
        else "Any channel"
    )
    return EmbedBuilder.info(
        "⚙ Mech Arena Database Assistant",
        "Source snapshots are immutable and separate. Answers use only approved "
        "records; missing or conflicting values are not guessed.\n\n"
        f"**Member questions:** "
        f"{'✅ Enabled' if guild_settings and guild_settings.enabled else '⏸ Disabled'}\n"
        f"**Question channel:** {question_channel}\n\n"
        + _format_status(await MechArenaService.status()),
    )


class MechArenaAdminView(ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.add_item(MechArenaQuestionChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await PermissionService().check_admin_interaction(interaction)

    @ui.button(label="🔄 Sync Sources", style=discord.ButtonStyle.primary)
    async def sync(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        result = await MechArenaService.refresh_sources(force=True)
        description = (
            f"Google Sheet: {result['google_sheet'].get('message')}\n"
            f"Calculator: {result['calculator'].get('message')}"
        )
        await interaction.followup.send(
            embed=EmbedBuilder.success("Source Refresh Complete", description),
            ephemeral=True,
        )

    @ui.button(label="📊 Status", style=discord.ButtonStyle.secondary)
    async def status(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=await mech_arena_admin_embed(self.guild),
            view=self,
        )

    @ui.button(label="✅ Enable / Disable", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: ui.Button):
        current = await MechArenaService.ensure_guild_settings(self.guild.id)
        item = await MechArenaService.set_guild_enabled(
            self.guild.id, not current.enabled, interaction.user.id
        )
        await interaction.response.edit_message(
            embed=EmbedBuilder.success(
                "Assistant Updated",
                "Member questions are now enabled." if item.enabled
                else "Member questions are now disabled.",
            ),
            view=self,
        )

    @ui.button(label="↩ Community Systems", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.community_systems import CommunitySystemsView, community_systems_embed

        await interaction.response.edit_message(
            embed=await community_systems_embed(self.guild, self.bot),
            view=CommunitySystemsView(self.bot, self.guild),
        )


class MechArenaQuestionChannelSelect(ui.ChannelSelect):
    def __init__(self, parent: MechArenaAdminView):
        self.parent_view = parent
        super().__init__(
            placeholder="Restrict member questions to a channel (optional)",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await MechArenaService.set_question_channel(
            self.parent_view.guild.id, channel.id, interaction.user.id
        )
        await interaction.response.edit_message(
            embed=EmbedBuilder.success(
                "Question Channel Saved",
                f"Members must now mention the bot in {channel.mention}.",
            ),
            view=self.parent_view,
        )


class MechArenaQuestionModal(ui.Modal, title="Ask Mech Arena Assistant"):
    question = ui.TextInput(
        label="Your question",
        placeholder="Example: What is Panther's max HP?",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=True,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await answer_question(interaction, self.question.value)


async def answer_question(interaction: discord.Interaction, question: str) -> None:
    if not interaction.guild:
        await interaction.response.send_message(
            embed=EmbedBuilder.error("Server Only", "Use this assistant inside a server."),
            ephemeral=True,
        )
        return
    settings = await MechArenaService.ensure_guild_settings(interaction.guild.id)
    if not settings.enabled:
        await interaction.response.send_message(
            embed=EmbedBuilder.warning(
                "Assistant Disabled",
                "An administrator must enable the Mech Arena assistant first.",
            ),
            ephemeral=True,
        )
        return
    await interaction.response.defer(ephemeral=True)
    attempted, result = await MechArenaService.calculate_from_question(question)
    if attempted:
        if not result.get("ok"):
            await interaction.followup.send(
                embed=EmbedBuilder.warning("Calculation Unavailable", result["message"]),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=EmbedBuilder.info("Verified Upgrade Cost", _calculation_text(result)),
            ephemeral=True,
        )
        return
    evidence = await MechArenaService.evidence(question)
    if evidence["stale_sources"]:
        await interaction.followup.send(
            embed=EmbedBuilder.warning(
                "Verified Data Is Stale",
                "I cannot answer until these sources are refreshed: "
                + ", ".join(evidence["stale_sources"]),
            ),
            ephemeral=True,
        )
        return
    if not evidence["matches"]:
        await interaction.followup.send(
            embed=EmbedBuilder.warning(
                "Not Found in Verified Data",
                "I could not find an exact supporting record, so I will not guess.",
            ),
            ephemeral=True,
        )
        return
    if evidence["conflicts"]:
        await interaction.followup.send(
            embed=EmbedBuilder.warning(
                "Conflicting Verified Records",
                "The available sources disagree, so I will not choose a value.",
            ),
            ephemeral=True,
        )
        return
    answer = await groq_broker.answer(question, evidence)
    answer += "\n\n" + " · ".join(
        f"{source}: {timestamp[:19].replace('T', ' ')} UTC"
        for source, timestamp in evidence["sources"].items()
        if timestamp
    )
    await interaction.followup.send(
        embed=EmbedBuilder.info("Mech Arena Assistant", answer[:4000]),
        ephemeral=True,
    )


async def answer_message(message: discord.Message, question: str) -> None:
    """Answer a bot mention in-channel without exposing API credentials."""
    if not message.guild:
        return
    settings = await MechArenaService.ensure_guild_settings(message.guild.id)
    if not settings.enabled:
        return
    if settings.question_channel_id and settings.question_channel_id != message.channel.id:
        return
    async with message.channel.typing():
        if settings.website_refresh_on_query and (
            "upgrade" in question.lower() or "cost" in question.lower()
        ):
            await MechArenaService.refresh_calculator()
        attempted, result = await MechArenaService.calculate_from_question(question)
        if attempted:
            if not result.get("ok"):
                await message.reply(
                    embed=EmbedBuilder.warning("Calculation Unavailable", result["message"]),
                    mention_author=False,
                )
                return
            await message.reply(
                embed=EmbedBuilder.info("Verified Upgrade Cost", _calculation_text(result)),
                mention_author=False,
            )
            return
        evidence = await MechArenaService.evidence(question)
        if evidence["stale_sources"]:
            await message.reply(
                embed=EmbedBuilder.warning(
                    "Verified Data Is Stale",
                    "I cannot answer until these sources are refreshed: "
                    + ", ".join(evidence["stale_sources"]),
                ),
                mention_author=False,
            )
            return
        if not evidence["matches"]:
            await message.reply(
                embed=EmbedBuilder.warning(
                    "Not Found in Verified Data",
                    "I could not find an exact supporting record, so I will not guess.",
                ),
                mention_author=False,
            )
            return
        if evidence["conflicts"]:
            await message.reply(
                embed=EmbedBuilder.warning(
                    "Conflicting Verified Records",
                    "The available sources disagree, so I will not choose a value.",
                ),
                mention_author=False,
            )
            return
        answer = await groq_broker.answer(question, evidence)
        answer += "\n\n" + " · ".join(
            f"{source}: {timestamp[:19].replace('T', ' ')} UTC"
            for source, timestamp in evidence["sources"].items()
            if timestamp
        )
        await message.reply(
            embed=EmbedBuilder.info("Mech Arena Assistant", answer[:4000]),
            mention_author=False,
        )