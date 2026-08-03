import discord
from discord import ui
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import Team
from bot.embeds.base import EmbedBuilder
from bot.services.team_deletion_service import TeamDeletionService

logger = get_logger(__name__)


class TeamDeleteConfirmationView(ui.View):
    def __init__(self, bot, guild, executor, team: Team):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team

    @ui.button(label="🗑 Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        service = TeamDeletionService(self.bot)
        result = await service.delete_team(self.guild, self.executor, self.team)

        if result.success:
            await interaction.followup.send(
                embed=EmbedBuilder.success("Team Deleted", result.message),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Deletion Failed", result.message),
                ephemeral=True
            )

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=EmbedBuilder.info("Cancelled", "Team deletion cancelled."),
            view=None
        )
