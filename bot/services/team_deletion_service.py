import discord
from dataclasses import dataclass
from app_logging.logger import get_logger
from database.engine import get_db_session
from models.models import Team, TeamMember, Role as DbRole, Channel as DbChannel
from sqlalchemy import select, delete
from bot.services.audit_service import AuditService

logger = get_logger(__name__)


@dataclass
class DeletionResult:
    success: bool
    message: str = ""


class TeamDeletionService:
    def __init__(self, bot):
        self.bot = bot

    async def delete_team(self, guild: discord.Guild, executor, team: Team) -> DeletionResult:
        async with get_db_session() as session:
            try:
                await AuditService.log_action(
                    guild_id=guild.id,
                    executor_id=executor.id,
                    action="TEAM_DELETION_STARTED",
                    metadata={"team_id": team.id, "display_name": team.display_name}
                )

                # Resilient deletion - continue even if individual steps fail
                errors = []

                # 1. Channels
                for ch_id in [team.plan_channel_id, team.discussion_channel_id,
                              team.opponents_channel_id, team.players_channel_id]:
                    if ch_id:
                        try:
                            ch = guild.get_channel(ch_id)
                            if ch:
                                await ch.delete(reason=f"Team {team.display_name} deletion")
                        except Exception as e:
                            errors.append(f"channel_{ch_id}")

                # 2. Category
                if team.category_id:
                    try:
                        cat = guild.get_channel(team.category_id)
                        if cat:
                            await cat.delete(reason=f"Team {team.display_name} deletion")
                    except Exception:
                        errors.append("category")

                # 3. Roles
                for role_id in [team.team_role_id, team.team_leader_role_id]:
                    if role_id:
                        try:
                            role = guild.get_role(role_id)
                            if role:
                                await role.delete(reason=f"Team {team.display_name} deletion")
                        except Exception:
                            errors.append(f"role_{role_id}")

                # 4. Database cleanup
                await session.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
                await session.execute(delete(DbRole).where(DbRole.team_id == team.id))
                await session.execute(delete(DbChannel).where(DbChannel.team_id == team.id))
                await session.delete(team)
                await session.commit()

                await AuditService.log_action(
                    guild_id=guild.id,
                    executor_id=executor.id,
                    action="TEAM_DELETED",
                    metadata={"team_id": team.id, "display_name": team.display_name, "errors": errors}
                )

                msg = f"{team.display_name} deleted." + (" Some resources may remain." if errors else "")
                return DeletionResult(True, msg)

            except Exception as e:
                await session.rollback()
                logger.error("team_deletion.failed", error=str(e), team_id=team.id)
                await AuditService.log_action(
                    guild_id=guild.id,
                    executor_id=executor.id,
                    action="TEAM_DELETION_FAILED",
                    metadata={"team_id": team.id, "error": str(e)}
                )
                return DeletionResult(False, "Failed to completely delete team.")
