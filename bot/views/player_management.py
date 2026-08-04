import discord
from discord import ui
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import Team, TeamMember, Player, Role as DbRole, RoleType
from sqlalchemy import select
from bot.embeds.base import EmbedBuilder
from bot.services.audit_service import AuditService

logger = get_logger(__name__)


class PlayerManagementView(ui.View):
    def __init__(self, bot, guild: discord.Guild, executor: discord.Member, team: Team):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team

    @ui.button(label="➕ Add Players", style=discord.ButtonStyle.success)
    async def add_players(self, interaction: discord.Interaction, button: ui.Button):
        view = AddPlayersView(self.bot, self.guild, self.executor, self.team)
        embed = EmbedBuilder.info("Add Players", "Select one or more members to add to this team.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="➖ Remove Players", style=discord.ButtonStyle.danger)
    async def remove_players(self, interaction: discord.Interaction, button: ui.Button):
        view = RemovePlayersView(self.bot, self.guild, self.executor, self.team)
        embed = EmbedBuilder.info("Remove Players", "Select members to remove from this team.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="👥 View Players", style=discord.ButtonStyle.secondary)
    async def view_players(self, interaction: discord.Interaction, button: ui.Button):
        async with get_db_session() as session:
            result = await session.execute(
                select(Player.display_name, Player.username, Player.user_id)
                .join(TeamMember, TeamMember.player_id == Player.id)
                .where(TeamMember.team_id == self.team.id)
            )
            players = result.all()

            player_names = []
            for p in players:
                name = p.display_name or p.username or str(p.user_id)
                player_names.append(name)

        embed = EmbedBuilder.info(
            f"{self.team.display_name} — Players",
            "\n".join(player_names) if player_names else "No players yet."
        )
        embed.add_field(name="Total", value=str(len(player_names)))
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AddPlayersView(ui.View):
    def __init__(self, bot, guild, executor, team):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team
        self.add_item(AddPlayerSelect(bot, guild, executor, team))


class AddPlayerSelect(ui.UserSelect):
    def __init__(self, bot, guild, executor, team):
        super().__init__(
            placeholder="Select members to add...",
            min_values=1,
            max_values=25
        )
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        added_count = 0
        team_role = self.guild.get_role(self.team.team_role_id)

        if not team_role:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "Team role not found."),
                ephemeral=True
            )
            return

        for user in self.values:
            if not isinstance(user, discord.Member):
                continue

            # Add role
            try:
                await user.add_roles(team_role, reason=f"Added to {self.team.display_name}")
            except discord.HTTPException:
                continue

            # Database
            async with get_db_session() as session:
                # Ensure player record
                player_result = await session.execute(
                    select(Player).where(Player.user_id == user.id)
                )
                player = player_result.scalar_one_or_none()
                if not player:
                    player = Player(user_id=user.id, username=str(user), display_name=user.display_name)
                    session.add(player)
                    await session.flush()

                # Check existing membership
                existing = await session.execute(
                    select(TeamMember).where(
                        TeamMember.team_id == self.team.id,
                        TeamMember.player_id == player.id
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                session.add(TeamMember(
                    team_id=self.team.id,
                    player_id=player.id,
                    is_team_leader=False
                ))
                await session.commit()

                await AuditService.log_action(
                    guild_id=self.guild.id,
                    executor_id=self.executor.id,
                    action="PLAYER_ADDED",
                    audit_metadata={"team_id": self.team.id, "player_id": player.id}
                )

            added_count += 1

        await interaction.followup.send(
            embed=EmbedBuilder.success(
                "Players Added",
                f"Successfully added {added_count} player(s) to {self.team.display_name}."
            ),
            ephemeral=True
        )


class RemovePlayersView(ui.View):
    def __init__(self, bot, guild, executor, team):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team
        self.add_item(RemovePlayerSelect(bot, guild, executor, team))


class RemovePlayerSelect(ui.UserSelect):
    def __init__(self, bot, guild, executor, team):
        super().__init__(
            placeholder="Select members to remove...",
            min_values=1,
            max_values=25
        )
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.team = team

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        removed_count = 0
        team_role = self.guild.get_role(self.team.team_role_id)

        if not team_role:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "Team role not found."),
                ephemeral=True
            )
            return

        for user in self.values:
            if not isinstance(user, discord.Member):
                continue

            # Remove role (but never touch Team Leader role)
            try:
                if team_role in user.roles:
                    await user.remove_roles(team_role, reason=f"Removed from {self.team.display_name}")
            except discord.HTTPException:
                pass

            async with get_db_session() as session:
                player_result = await session.execute(
                    select(Player).where(Player.user_id == user.id)
                )
                player = player_result.scalar_one_or_none()
                if not player:
                    continue

                result = await session.execute(
                    select(TeamMember).where(
                        TeamMember.team_id == self.team.id,
                        TeamMember.player_id == player.id
                    )
                )
                membership = result.scalar_one_or_none()
                if membership:
                    await session.delete(membership)
                    await session.commit()

                    await AuditService.log_action(
                        guild_id=self.guild.id,
                        executor_id=self.executor.id,
                        action="PLAYER_REMOVED",
                        audit_metadata={"team_id": self.team.id, "player_id": player.id}
                    )
                    removed_count += 1

        await interaction.followup.send(
            embed=EmbedBuilder.success(
                "Players Removed",
                f"Successfully removed {removed_count} player(s) from {self.team.display_name}."
            ),
            ephemeral=True
        )
