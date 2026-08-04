import discord
from discord import ui
from typing import List
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import Team
from sqlalchemy import select
from bot.embeds.base import EmbedBuilder
from bot.views.player_management import PlayerManagementView

logger = get_logger(__name__)


class TeamSelectionView(ui.View):
    """View for selecting a team to manage players."""

    def __init__(self, bot, guild: discord.Guild, executor: discord.Member):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.add_item(TeamSelect(bot, guild, executor))


class TeamSelect(ui.Select):
    def __init__(self, bot, guild: discord.Guild, executor: discord.Member):
        self.bot = bot
        self.guild = guild
        self.executor = executor

        super().__init__(
            placeholder="Select a team...",
            min_values=1,
            max_values=1,
            options=[]
        )
        self._load_teams()

    async def _load_teams(self):
        async with get_db_session() as session:
            result = await session.execute(
                select(Team).where(Team.guild_id == self.guild.id).order_by(Team.team_number)
            )
            teams = result.scalars().all()

            options = []
            for team in teams:
                label = team.display_name
                options.append(discord.SelectOption(
                    label=label,
                    value=str(team.id),
                    description=f"Team #{team.team_number}"
                ))

            if options:
                self.options = options[:25]  # Discord limit
            else:
                self.options = [discord.SelectOption(label="No teams found", value="none")]

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                embed=EmbedBuilder.warning("No Teams", "No teams have been created yet."),
                ephemeral=True
            )
            return

        team_id = int(self.values[0])

        async with get_db_session() as session:
            result = await session.execute(select(Team).where(Team.id == team_id))
            team = result.scalar_one_or_none()

            if not team:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Error", "Team not found."),
                    ephemeral=True
                )
                return

        view = PlayerManagementView(self.bot, self.guild, self.executor, team)
        embed = EmbedBuilder.info(
            f"Manage {team.display_name}",
            f"**SP Range:** {team.sp_range or 'N/A'}\n"
            f"**Players:** Use the buttons below to manage members."
        )
        await interaction.response.edit_message(embed=embed, view=view)
