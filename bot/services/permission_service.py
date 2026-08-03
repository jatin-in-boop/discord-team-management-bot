import discord
from app_logging.logger import get_logger

logger = get_logger(__name__)


class PermissionService:
    """Reusable permission verification service."""

    def is_admin(self, user: discord.abc.User) -> bool:
        if isinstance(user, discord.Member):
            return user.guild_permissions.administrator
        return False

    async def check_admin_interaction(self, interaction: discord.Interaction) -> bool:
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Permission Denied",
                    description="Only server administrators may perform this action.",
                    color=0xED4245
                ),
                ephemeral=True
            )
            return False
        return True
