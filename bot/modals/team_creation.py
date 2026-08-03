import discord
from discord import ui
from typing import Optional
from app_logging.logger import get_logger
from bot.services.team_creation import TeamCreationService
from bot.embeds.base import EmbedBuilder

logger = get_logger(__name__)


class TeamCreationModal(ui.Modal, title="Create New Team"):
    team_number = ui.TextInput(
        label="Team Number",
        placeholder="1",
        required=True,
        max_length=5,
        style=discord.TextStyle.short
    )

    sp_range = ui.TextInput(
        label="SP Range",
        placeholder="7000-8000",
        required=True,
        max_length=20,
        style=discord.TextStyle.short
    )

    def __init__(self, bot, guild: discord.Guild, executor: discord.Member):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.executor = executor

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            team_number = int(self.team_number.value.strip())
            sp_range = self.sp_range.value.strip()

            if team_number < 1:
                raise ValueError("Team number must be positive")

            if not self._validate_sp_range(sp_range):
                raise ValueError("SP Range must be in format NUMBER-NUMBER (e.g. 7000-8000)")

            service = TeamCreationService(self.bot)
            result = await service.create_team(
                guild=self.guild,
                executor=self.executor,
                team_number=team_number,
                sp_range=sp_range
            )

            if result.success:
                # Open player selection immediately after creation (Phase 2 requirement)
                from bot.views.player_management import AddPlayersView
                from database.engine import get_db_session
                from models.models import Team
                from sqlalchemy import select

                async with get_db_session() as session:
                    team = (await session.execute(select(Team).where(Team.id == result.team_id))).scalar_one_or_none()

                if team:
                    view = AddPlayersView(self.bot, self.guild, self.executor, team)
                    await interaction.followup.send(
                        embed=EmbedBuilder.success(
                            "Team Created Successfully",
                            f"**{result.team_name}**\n"
                            f"Category: {result.category_name}\n\n"
                            "Select players to add to the team below."
                        ),
                        view=view,
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=EmbedBuilder.success(
                            "Team Created Successfully",
                            f"**{result.team_name}**\n"
                            f"Category: {result.category_name}\n\n"
                            "The Team Leader role has been created. "
                            "Assign it manually through Discord."
                        ),
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    embed=EmbedBuilder.error("Team Creation Failed", result.error_message),
                    ephemeral=True
                )

        except ValueError as ve:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Invalid Input", str(ve)),
                ephemeral=True
            )
        except Exception as e:
            logger.error("team_creation.modal_error", error=str(e))
            await interaction.followup.send(
                embed=EmbedBuilder.error("Unexpected Error", "Please try again or contact an administrator."),
                ephemeral=True
            )

    def _validate_sp_range(self, sp_range: str) -> bool:
        import re
        return bool(re.match(r"^\d+-\d+$", sp_range))
