from __future__ import annotations

import discord
from discord import ui

from bot.embeds.base import EmbedBuilder
from bot.services.giveaway_service import GiveawayService


class GiveawayMemberView(ui.View):
    def __init__(self, bot, giveaway_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.giveaway_id = giveaway_id
        # Persistent views must have unique component IDs when multiple
        # giveaways are active at once.
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id:
                item.custom_id = f"{item.custom_id}:{giveaway_id}"

    @ui.button(
        label="🎟 Enter Giveaway",
        style=discord.ButtonStyle.success,
        custom_id="giveaway_enter",
    )
    async def enter(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Server Only", "This giveaway is available in a server."),
                ephemeral=True,
            )
            return
        ok, message = await GiveawayService(self.bot).enter(
            interaction.guild, interaction.user, self.giveaway_id
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Entry Confirmed", message)
            if ok else EmbedBuilder.warning("Entry Not Added", message),
            ephemeral=True,
        )

    @ui.button(
        label="📋 View Rules",
        style=discord.ButtonStyle.secondary,
        custom_id="giveaway_rules",
    )
    async def rules(self, interaction: discord.Interaction, button: ui.Button):
        giveaway = await GiveawayService(self.bot).get(self.giveaway_id)
        if not giveaway:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Unavailable", "This giveaway no longer exists."),
                ephemeral=True,
            )
            return
        eligibility = giveaway.eligibility_config or {}
        rules = (
            f"**Prize:** {giveaway.prize_description}\n"
            f"**Winners:** {giveaway.winner_count}\n"
            f"**Ends:** <t:{int(giveaway.end_at.timestamp())}:F>\n"
            f"**Required roles:** {len(eligibility.get('required_role_ids', [])) or 'None'}\n\n"
            "The bot conducts the draw only. The organizer is responsible for "
            "providing and delivering the prize."
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.info("📋 Giveaway Rules", rules), ephemeral=True
        )

    @ui.button(
        label="✅ Claim Prize",
        style=discord.ButtonStyle.primary,
        custom_id="giveaway_claim",
        row=1,
    )
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        ok, message = await GiveawayService(self.bot).claim(
            interaction.guild, interaction.user, self.giveaway_id
        )
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Claim Recorded", message)
            if ok else EmbedBuilder.warning("Claim Unavailable", message),
            ephemeral=True,
        )