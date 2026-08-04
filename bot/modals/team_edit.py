import discord
from discord import ui
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import Team
from sqlalchemy import select
from bot.embeds.base import EmbedBuilder
from bot.services.team_edit_service import TeamEditService

logger = get_logger(__name__)


class EditTeamModal(ui.Modal, title="Edit Team"):
    new_value = ui.TextInput(
        label="New Value",
        placeholder="",
        required=True,
        max_length=30,
        style=discord.TextStyle.short
    )

    def __init__(self, bot, guild, executor, team: Team, edit_type: str):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team
        self.edit_type = edit_type

        if edit_type == "number":
            self.title = "Edit Team Number"
            self.new_value.label = "New Team Number"
            self.new_value.placeholder = str(team.team_number)
        else:
            self.title = "Edit SP Range"
            self.new_value.label = "New SP Range"
            self.new_value.placeholder = team.sp_range or "7000-8000"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            service = TeamEditService(self.bot)
            result = await service.edit_team(
                guild=self.guild,
                executor=self.executor,
                team=self.team,
                edit_type=self.edit_type,
                new_value=self.new_value.value.strip()
            )

            if result.success:
                await interaction.followup.send(
                    embed=EmbedBuilder.success("Team Updated", result.message),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=EmbedBuilder.error("Update Failed", result.message),
                    ephemeral=True
                )
        except Exception as e:
            logger.error("team_edit.modal_error", error=str(e))
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "An unexpected error occurred."),
                ephemeral=True
            )
