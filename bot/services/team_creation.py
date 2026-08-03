import discord
from dataclasses import dataclass
from typing import Optional, List
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import (
    Guild as DbGuild, Team, Role as DbRole, Channel as DbChannel,
    TeamMember, Player, RoleType, ChannelType, AuditLog
)
from sqlalchemy import select
from bot.services.audit_service import AuditService

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
                team_role_name = f"TEAM {team_number} {sp_range} SP"
                leader_role_name = f"TEAM LEADER • TEAM {team_number} {sp_range} SP"

                team_role = await guild.create_role(
                    name=team_role_name,
                    mentionable=True,
                    reason=f"Team {team_number} creation"
                )

                leader_role = await guild.create_role(
                    name=leader_role_name,
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
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
        }
        for member in guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True)

        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True)
        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True)

        return await guild.create_category_channel(name, overwrites=overwrites)

    async def _create_channels(self, guild, category, team_role, leader_role):
        channels = {}

        # Plan (Announcement)
        plan = await guild.create_text_channel(
            "📢｜plan",
            category=category,
            overwrites={
                team_role: discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=False),
                leader_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True),
            }
        )
        channels["plan"] = plan

        # Discussion
        discussion = await guild.create_text_channel(
            "💬｜team-discussion",
            category=category,
            overwrites={
                team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True),
                leader_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True),
            }
        )
        channels["discussion"] = discussion

        # Opponents
        opponents = await guild.create_text_channel(
            "🆚｜opponents-ids-and-hangers",
            category=category,
            overwrites={
                team_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                leader_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True),
            }
        )
        channels["opponents"] = opponents

        # Players
        players = await guild.create_text_channel(
            "👤｜player-ids-and-hangers",
            category=category,
            overwrites={
                team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True),
            }
        )
        channels["players"] = players

        return channels

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
