import discord
from dataclasses import dataclass
from typing import Optional, List
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import (
    Guild as DbGuild, Team, Role as DbRole, Channel as DbChannel,
    TeamMember, Player, RoleType, ChannelType, AuditLog
)
from sqlalchemy import select
from bot.services.audit_service import AuditService
from bot.services.team_style import channel_name, role_colors, role_names

logger = get_logger(__name__)


@dataclass
class TeamCreationResult:
    success: bool
    team_name: Optional[str] = None
    category_name: Optional[str] = None
    players_added: int = 0
    error_message: Optional[str] = None
    team_id: Optional[int] = None


class TeamCreationService:
    def __init__(self, bot):
        self.bot = bot

    async def create_team(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        team_number: int,
        sp_range: str
    ) -> TeamCreationResult:

        async with get_db_session() as session:
            # Duplicate check
            result = await session.execute(
                select(Team).where(
                    Team.guild_id == guild.id,
                    Team.team_number == team_number
                )
            )
            if result.scalar_one_or_none():
                return TeamCreationResult(success=False, error_message="Team number already exists in this server.")

            try:
                # 1. Create Roles
                team_role_name, leader_role_name = role_names(team_number, sp_range)

                team_role = await guild.create_role(
                    name=team_role_name,
                    color=role_colors(team_number)[0],
                    mentionable=True,
                    reason=f"Team {team_number} creation"
                )

                leader_role = await guild.create_role(
                    name=leader_role_name,
                    color=role_colors(team_number)[1],
                    mentionable=True,
                    reason=f"Team Leader role for Team {team_number}"
                )

                # Position roles below bot
                await self._position_roles(guild, [team_role, leader_role])

                # 2. Create Category
                category_name = f"TEAM {team_number} {sp_range} SP"
                category = await self._create_category(guild, category_name, team_role, leader_role)

                # 3. Create Channels
                channels = await self._create_channels(guild, category, team_role, leader_role)

                # 4. Save to database
                db_team = Team(
                    guild_id=guild.id,
                    team_number=team_number,
                    sp_range=sp_range,
                    display_name=category_name,
                    category_id=category.id,
                    team_role_id=team_role.id,
                    team_leader_role_id=leader_role.id,
                    plan_channel_id=channels["plan"].id,
                    discussion_channel_id=channels["discussion"].id,
                    opponents_channel_id=channels["opponents"].id,
                    players_channel_id=channels["players"].id,
                )
                session.add(db_team)
                await session.flush()

                # Save roles
                for role, role_type in [(team_role, RoleType.TEAM), (leader_role, RoleType.TEAM_LEADER)]:
                    session.add(DbRole(
                        guild_id=guild.id,
                        team_id=db_team.id,
                        discord_role_id=role.id,
                        role_type=role_type
                    ))

                # Save channels
                channel_map = {
                    "plan": (channels["plan"], ChannelType.PLAN),
                    "discussion": (channels["discussion"], ChannelType.DISCUSSION),
                    "opponents": (channels["opponents"], ChannelType.OPPONENTS),
                    "players": (channels["players"], ChannelType.PLAYERS),
                }
                for ch, ch_type in channel_map.values():
                    session.add(DbChannel(
                        guild_id=guild.id,
                        team_id=db_team.id,
                        discord_channel_id=ch.id,
                        channel_type=ch_type
                    ))

                await session.commit()

                # 5. Audit log
                await AuditService.log_action(
                    guild_id=guild.id,
                    executor_id=executor.id,
                    action="TEAM_CREATED",
                    metadata={
                        "team_number": team_number,
                        "sp_range": sp_range,
                        "team_role_id": team_role.id,
                        "leader_role_id": leader_role.id,
                        "category_id": category.id
                    }
                )

                return TeamCreationResult(
                    success=True,
                    team_name=category_name,
                    category_name=category_name,
                    players_added=0,
                    team_id=db_team.id   # NEW: expose team id for player selection
                )

            except Exception as e:
                logger.error("team_creation.failed", error=str(e), guild_id=guild.id)
                await self._cleanup_failed_creation(guild, team_role, leader_role, category, channels)
                await session.rollback()
                return TeamCreationResult(success=False, error_message="Failed to create team resources.")

    async def _position_roles(self, guild: discord.Guild, roles: List[discord.Role]):
        try:
            bot_member = guild.me
            if bot_member.top_role:
                target_position = bot_member.top_role.position - 1
                for role in roles:
                    await role.edit(position=max(target_position, 1))
        except Exception:
            pass  # Non-critical

    async def _create_category(self, guild, name, team_role, leader_role):
        return await guild.create_category_channel(
            name,
            overwrites=self._category_overwrites(guild, team_role, leader_role),
        )

    async def _create_channels(self, guild, category, team_role, leader_role):
        channels = {}

        # Plan (Announcement)
        plan = await guild.create_text_channel(
            channel_name("plan"),
            category=category,
            overwrites=self._channel_overwrites(
                guild, team_role, leader_role, "plan"
            ),
        )
        channels["plan"] = plan

        # Discussion
        discussion = await guild.create_text_channel(
            channel_name("discussion"),
            category=category,
            overwrites=self._channel_overwrites(
                guild, team_role, leader_role, "discussion"
            ),
        )
        channels["discussion"] = discussion

        # Opponents
        opponents = await guild.create_text_channel(
            channel_name("opponents"),
            category=category,
            overwrites=self._channel_overwrites(
                guild, team_role, leader_role, "opponents"
            ),
        )
        channels["opponents"] = opponents

        # Players
        players = await guild.create_text_channel(
            channel_name("players"),
            category=category,
            overwrites=self._channel_overwrites(
                guild, team_role, leader_role, "players"
            ),
        )
        channels["players"] = players

        return channels

    def _base_private_overwrites(self, guild):
        """Return the explicit allow-list shared by private team resources."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True,
            )

        for member in guild.members:
            if member.guild_permissions.administrator and (
                not guild.me or member.id != guild.me.id
            ):
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=True,
                )

        return overwrites

    def _category_overwrites(self, guild, team_role, leader_role):
        overwrites = self._base_private_overwrites(guild)
        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True)
        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True)
        return overwrites

    def _channel_overwrites(self, guild, team_role, leader_role, channel_type):
        overwrites = self._base_private_overwrites(guild)
        can_write = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
        )
        read_only = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
        )

        if channel_type == "plan":
            overwrites[team_role] = read_only
            overwrites[leader_role] = can_write
        elif channel_type == "opponents":
            overwrites[team_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
            )
            overwrites[leader_role] = can_write
        else:
            overwrites[team_role] = can_write
            overwrites[leader_role] = can_write

        return overwrites

    async def repair_guild_permissions(self, guild: discord.Guild) -> int:
        """Repair visibility on existing team categories and channels."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Team).where(Team.guild_id == guild.id)
            )
            teams = result.scalars().all()

        repaired = 0
        for team in teams:
            team_role = guild.get_role(team.team_role_id)
            leader_role = guild.get_role(team.team_leader_role_id)
            category = guild.get_channel(team.category_id) if team.category_id else None

            if not team_role or not leader_role:
                logger.warning(
                    "team_permissions.roles_missing",
                    guild_id=guild.id,
                    team_id=team.id,
                )
                continue

            try:
                team_role_name, leader_role_name = role_names(
                    team.team_number, team.sp_range
                )
                team_color, leader_color = role_colors(team.team_number)
                if team_role.name != team_role_name or team_role.color != team_color:
                    await team_role.edit(
                        name=team_role_name,
                        color=team_color,
                        reason="Team styling repair",
                    )
                    repaired += 1
                if leader_role.name != leader_role_name or leader_role.color != leader_color:
                    await leader_role.edit(
                        name=leader_role_name,
                        color=leader_color,
                        reason="Team styling repair",
                    )
                    repaired += 1

                if isinstance(category, discord.CategoryChannel):
                    await category.edit(
                        overwrites=self._category_overwrites(
                            guild, team_role, leader_role
                        )
                    )
                    repaired += 1

                channel_map = {
                    "plan": team.plan_channel_id,
                    "discussion": team.discussion_channel_id,
                    "opponents": team.opponents_channel_id,
                    "players": team.players_channel_id,
                }
                for channel_type, channel_id in channel_map.items():
                    channel = guild.get_channel(channel_id) if channel_id else None
                    if isinstance(channel, discord.TextChannel):
                        await channel.edit(
                            name=channel_name(channel_type),
                            overwrites=self._channel_overwrites(
                                guild, team_role, leader_role, channel_type
                            )
                        )
                        repaired += 1
            except discord.HTTPException as error:
                logger.error(
                    "team_permissions.repair_failed",
                    guild_id=guild.id,
                    team_id=team.id,
                    error=str(error),
                )

        return repaired

    async def _cleanup_failed_creation(self, guild, team_role, leader_role, category, channels):
        """Rollback created Discord resources on failure."""
        try:
            if channels:
                for ch in channels.values():
                    if ch:
                        await ch.delete(reason="Team creation failed - cleanup")
            if category:
                await category.delete(reason="Team creation failed - cleanup")
            if leader_role:
                await leader_role.delete(reason="Team creation failed - cleanup")
            if team_role:
                await team_role.delete(reason="Team creation failed - cleanup")
        except Exception as e:
            logger.error("team_creation.cleanup_failed", error=str(e))
