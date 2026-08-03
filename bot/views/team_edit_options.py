import discord
from discord import ui
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import Team
from bot.embeds.base import EmbedBuilder
from bot.modals.team_edit import EditTeamModal
from bot.services.team_edit_service import TeamEditService

logger = get_logger(__name__)


class TeamEditOptionsView(ui.View):
    def __init__(self, bot, guild, executor, team: Team):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team

    @ui.button(label="📝 Edit Team Number", style=discord.ButtonStyle.primary)
    async def edit_number(self, interaction: discord.Interaction, button: ui.Button):
        modal = EditTeamModal(self.bot, self.guild, self.executor, self.team, edit_type="number")
        await interaction.response.send_modal(modal)

    @ui.button(label="📊 Edit SP Range", style=discord.ButtonStyle.primary)
    async def edit_sp(self, interaction: discord.Interaction, button: ui.Button):
        modal = EditTeamModal(self.bot, self.guild, self.executor, self.team, edit_type="sp_range")
        await interaction.response.send_modal(modal)

    @ui.button(label="🔄 Synchronize Team", style=discord.ButtonStyle.secondary)
    async def synchronize(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        service = TeamEditService(self.bot)
        result = await service.synchronize_team(self.guild, self.executor, self.team)

        if result.success:
            await interaction.followup.send(
                embed=EmbedBuilder.success("Synchronization Complete", result.message),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Synchronization Failed", result.message),
                ephemeral=True
            )
