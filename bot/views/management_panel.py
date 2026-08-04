import discord
from bot.embeds.base import EmbedBuilder
from app_logging.logger import get_logger
from bot.services.permission_service import PermissionService
from bot.modals.team_creation import TeamCreationModal

logger = get_logger(__name__)


class ManagementPanelView(discord.ui.View):
    """Persistent management panel view."""

    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        permission_service = PermissionService()
        if not permission_service.is_admin(interaction.user):
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Permission Denied",
                    "Only administrators may use the management panel."
                ),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="➕ Create Team", style=discord.ButtonStyle.success, custom_id="create_team")
    async def create_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Error", "This action can only be performed in a server."),
                ephemeral=True
            )
            return

        modal = TeamCreationModal(self.bot, interaction.guild, interaction.user)
        try:
            await interaction.response.send_modal(modal)
        except discord.NotFound:
            logger.warning(
                "management_panel.interaction_expired",
                action="create_team",
                interaction_id=interaction.id,
            )

    @discord.ui.button(label="👥 Manage Players", style=discord.ButtonStyle.primary, custom_id="manage_players")
    async def manage_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.views.team_selection import TeamSelectionView

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Error", "This action can only be performed in a server."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            view = await TeamSelectionView.create(self.bot, interaction.guild, interaction.user)
            embed = EmbedBuilder.info("Select Team", "Choose a team to manage its players.")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error("management_panel.manage_players_failed", error=str(e))
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "Unable to load teams. Please try again."),
                ephemeral=True
            )

    @discord.ui.button(label="✏ Edit Team", style=discord.ButtonStyle.secondary, custom_id="edit_team")
    async def edit_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.views.team_edit_selection import TeamEditSelectionView

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Error", "This action can only be performed in a server."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            view = await TeamEditSelectionView.create(self.bot, interaction.guild, interaction.user)
            embed = EmbedBuilder.info("Select Team", "Choose a team to edit.")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error("management_panel.edit_team_failed", error=str(e))
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "Unable to load teams. Please try again."),
                ephemeral=True
            )

    @discord.ui.button(label="🗑 Delete Team", style=discord.ButtonStyle.danger, custom_id="delete_team")
    async def delete_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.views.team_delete_selection import TeamDeleteSelectionView

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Error", "This action can only be performed in a server."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            view = await TeamDeleteSelectionView.create(self.bot, interaction.guild, interaction.user)
            embed = EmbedBuilder.warning("Select Team to Delete", "⚠️ This action is permanent. Choose carefully.")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error("management_panel.delete_team_failed", error=str(e))
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", "Unable to load teams. Please try again."),
                ephemeral=True
            )

    @discord.ui.button(
        label="✨ Community Features",
        style=discord.ButtonStyle.primary,
        custom_id="community_features",
        row=2,
    )
    async def community_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.views.community_features import CommunityFeaturesView, community_status_embed

        if not interaction.guild:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Error", "This action can only be performed in a server."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=await community_status_embed(interaction.guild),
            view=CommunityFeaturesView(interaction.client),
            ephemeral=True,
        )
