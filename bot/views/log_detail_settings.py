from __future__ import annotations

import discord
from discord import ui
from sqlalchemy import select

from bot.embeds.base import EmbedBuilder
from bot.services.server_log_service import ALL_CATEGORIES, DEFAULT_CATEGORIES
from database.session import get_db_session
from models.models import CommunitySettings


class LogDetailModal(ui.Modal, title="Server Log Detail Settings"):
    def __init__(self, parent, config: dict):
        super().__init__()
        self.parent = parent
        categories = config.get("categories") or DEFAULT_CATEGORIES
        self.categories = ui.TextInput(
            label="Categories",
            default=", ".join(categories),
            placeholder="moderation, members, channels, roles, invites, server, voice",
            required=True,
            max_length=200,
        )
        self.include_messages = ui.TextInput(
            label="Include message edits/deletions? yes/no",
            default="yes" if config.get("include_messages") else "no",
            required=True,
            max_length=3,
        )
        self.include_automation = ui.TextInput(
            label="Include bot automation? yes/no",
            default="yes" if config.get("include_automation") else "no",
            required=True,
            max_length=3,
        )
        for item in (self.categories, self.include_messages, self.include_automation):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        valid_categories = set(ALL_CATEGORIES)
        chosen = {
            item.strip().lower()
            for item in self.categories.value.split(",")
            if item.strip().lower() in valid_categories
        }
        if not chosen:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "No Categories Selected",
                    "Choose at least one category from the list shown in the field.",
                ),
                ephemeral=True,
            )
            return
        if self.include_messages.value.strip().lower() not in {"yes", "no"}:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Message Setting", "Enter yes or no."),
                ephemeral=True,
            )
            return
        if self.include_automation.value.strip().lower() not in {"yes", "no"}:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Automation Setting", "Enter yes or no."),
                ephemeral=True,
            )
            return
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(
                        CommunitySettings.guild_id == self.parent.guild.id
                    )
                )
            ).scalar_one_or_none()
            if settings:
                settings.audit_log_config = {
                    "categories": sorted(chosen),
                    "include_messages": self.include_messages.value.strip().lower() == "yes",
                    "include_automation": self.include_automation.value.strip().lower() == "yes",
                }
        await interaction.response.edit_message(
            embed=await self.parent.render_embed(),
            view=self.parent,
        )