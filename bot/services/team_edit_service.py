import discord
from dataclasses import dataclass
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import Team, Role as DbRole, Channel as DbChannel, RoleType, ChannelType
from sqlalchemy import select
from bot.services.audit_service import AuditService

logger = get_logger(__name__)


@dataclass
class EditResult:
    success: bool
    message: str = ""


class TeamEditService:
    def __init__(self, bot):
        self.bot = bot

    async def edit_team(self, guild: discord.Guild, executor, team: Team, edit_type: str, new_value: str) -> EditResult:
        async with get_db_session() as session:
            try:
                if edit_type == "number":
                    new_number = int(new_value)
                    if new_number < 1:
                        return EditResult(False, "Team number must be positive.")

                    # Check for duplicate
                    existing = await session.execute(
                        select(Team).where(Team.guild_id == guild.id, Team.team_number == new_number, Team.id != team.id)
                    )
                    if existing.scalar_one_or_none():
                        return EditResult(False, "Team number already in use.")

                    old_number = team.team_number
                    team.team_number = new_number

                elif edit_type == "sp_range":
                    import re
                    if not re.match(r"^\d+-\d+$", new_value):
                        return EditResult(False, "SP Range must be in format NUMBER-NUMBER.")
                    old_sp = team.sp_range
                    team.sp_range = new_value
                else:
                    return EditResult(False, "Invalid edit type.")

                # Generate new names
                new_display = f"TEAM {team.team_number} {team.sp_range} SP"
                new_team_role_name = new_display
                new_leader_role_name = f"TEAM LEADER • {new_display}"

                # Rename Discord resources
                team_role = guild.get_role(team.team_role_id)
                leader_role = guild.get_role(team.team_leader_role_id)
                category = guild.get_channel(team.category_id)

                if team_role:
                    await team_role.edit(name=new_team_role_name)
                if leader_role:
                    await leader_role.edit(name=new_leader_role_name)
                if category:
                    await category.edit(name=new_display)

                team.display_name = new_display
                await session.commit()

                await AuditService.log_action(
                    guild_id=guild.id,
                    executor_id=executor.id,
                    action="TEAM_EDITED",
                    audit_metadata={
                        "team_id": team.id,
                        "edit_type": edit_type,
                        "old_value": old_number if edit_type == "number" else old_sp,
                        "new_value": new_value
                    }
                )

                return EditResult(True, f"Team successfully updated to {new_display}.")

            except Exception as e:
                await session.rollback()
                logger.error("team_edit.failed", error=str(e))
                return EditResult(False, "Failed to update team.")

    async def synchronize_team(self, guild: discord.Guild, executor, team: Team) -> EditResult:
        async with get_db_session() as session:
            changes = []

            # Validate roles
            team_role = guild.get_role(team.team_role_id)
            leader_role = guild.get_role(team.team_leader_role_id)

            if not team_role:
                team_role = await guild.create_role(name=f"TEAM {team.team_number} {team.sp_range} SP")
                team.team_role_id = team_role.id
                changes.append("Recreated Team Role")

            if not leader_role:
                leader_role = await guild.create_role(name=f"TEAM LEADER • TEAM {team.team_number} {team.sp_range} SP")
                team.team_leader_role_id = leader_role.id
                changes.append("Recreated Team Leader Role")

            # Validate category
            category = guild.get_channel(team.category_id)
            if not category:
                category = await guild.create_category_channel(team.display_name)
                team.category_id = category.id
                changes.append("Recreated Category")

            # Validate channels + repair permissions
            channel_map = {
                ChannelType.PLAN: ("📢｜plan", team.plan_channel_id),
                ChannelType.DISCUSSION: ("💬｜team-discussion", team.discussion_channel_id),
                ChannelType.OPPONENTS: ("🆚｜opponents-ids-and-hangers", team.opponents_channel_id),
                ChannelType.PLAYERS: ("👤｜player-ids-and-hangers", team.players_channel_id),
            }

            team_role = guild.get_role(team.team_role_id)
            leader_role = guild.get_role(team.team_leader_role_id)

            for ch_type, (name, ch_id) in channel_map.items():
                ch = guild.get_channel(ch_id)
                if not ch:
                    ch = await guild.create_text_channel(name, category=category)
                    if ch_type == ChannelType.PLAN:
                        team.plan_channel_id = ch.id
                    elif ch_type == ChannelType.DISCUSSION:
                        team.discussion_channel_id = ch.id
                    elif ch_type == ChannelType.OPPONENTS:
                        team.opponents_channel_id = ch.id
                    elif ch_type == ChannelType.PLAYERS:
                        team.players_channel_id = ch.id
                    changes.append(f"Recreated {name}")
                    ch = guild.get_channel(ch.id)  # refresh

                # Re-apply correct permissions
                if ch and team_role and leader_role:
                    overwrites = ch.overwrites
                    if ch_type == ChannelType.PLAN:
                        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=False)
                        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                    elif ch_type == ChannelType.DISCUSSION:
                        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                    elif ch_type == ChannelType.OPPONENTS:
                        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
                        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                    elif ch_type == ChannelType.PLAYERS:
                        overwrites[team_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                        overwrites[leader_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, add_reactions=True)
                    await ch.edit(overwrites=overwrites)

            await session.commit()

            await AuditService.log_action(
                guild_id=guild.id,
                executor_id=executor.id,
                action="TEAM_SYNCHRONIZED",
                audit_metadata={"team_id": team.id, "changes": changes}
            )

            msg = "No issues found." if not changes else "Repaired: " + ", ".join(changes)
            return EditResult(True, msg)
