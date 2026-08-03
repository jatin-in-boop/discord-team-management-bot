import discord
from discord import ui
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import Team
from sqlalchemy import select
from bot.embeds.base import EmbedBuilder
from bot.views.team_delete_confirmation import TeamDeleteConfirmationView

logger = get_logger(__name__)


class TeamDeleteSelectionView(ui.View):
    def __init__(self, bot, guild: discord.Guild, executor: discord.Member):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.add_item(TeamDeleteSelect(bot, guild, executor))


class TeamDeleteSelect(ui.Select):
    def __init__(self, bot, guild, executor):
        super().__init__(placeholder="Select a team to delete...", min_values=1, max_values=1)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self._load_teams()

    async def _load_teams(self):
        async with get_db_session() as session:
            result = await session.execute(
                select(Team).where(Team.guild_id == self.guild.id).order_by(Team.team_number)
            )
            teams = result.scalars().all()
            options = [
                discord.SelectOption(label=team.display_name, value=str(team.id), description=f"Team #{team.team_number}")
                for team in teams
            ]
            self.options = options or [discord.SelectOption(label="No teams", value="none")]

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(embed=EmbedBuilder.warning("No Teams", "No teams available."), ephemeral=True)
            return

        team_id = int(self.values[0])
        async with get_db_session() as session:
            team = (await session.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()

        if not team:
            await interaction.response.send_message(embed=EmbedBuilder.error("Error", "Team not found."), ephemeral=True)
            return

        view = TeamDeleteConfirmationView(self.bot, self.guild, self.executor, team)
        embed = EmbedBuilder.warning(
            f"⚠️ Confirm Deletion of {team.display_name}",
            "This will permanently delete:\n"
            f"• Team Role\n• Team Leader Role\n• Category & all 4 channels\n• All player mappings\n\n"
            "**This action cannot be undone.**"
        )
        await interaction.response.edit_message(embed=embed, view=view)
