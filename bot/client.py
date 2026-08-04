import discord
from discord.ext import commands
from config.settings import get_settings
from app_logging.logger import get_logger
from database.engine import init_db, close_db
from bot.services.guild_setup import GuildSetupService
from bot.services.panel_restoration import PanelRestorationService
from bot.services.permission_service import PermissionService
from bot.services.team_creation import TeamCreationService
from bot.views.management_panel import ManagementPanelView

logger = get_logger(__name__)
settings = get_settings()


class TeamManagementBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None
        )

        self.setup_service = GuildSetupService(self)
        self.restoration_service = PanelRestorationService(self)
        self.team_creation_service = TeamCreationService(self)
        self.permission_service = PermissionService()
        self.persistent_views_registered = False

    async def setup_hook(self):
        logger.info("bot.startup.begin")

        # 1. Load configuration (already done via Pydantic)
        # 2. Initialize logging (already done)
        logger.info("bot.startup.config_loaded")

        # 3-4. Connect to Supabase & verify schema
        await init_db()
        logger.info("bot.startup.database_ready")

        # 5. Initialize services (done in __init__)
        logger.info("bot.startup.services_initialized")

        # 6. Register persistent views
        self.add_view(ManagementPanelView())
        self.persistent_views_registered = True
        logger.info("bot.startup.persistent_views_registered")

        logger.info("bot.startup.complete")

    async def on_ready(self):
        logger.info("bot.ready", user=str(self.user), guilds=len(self.guilds))

        from bot.services.health_service import HealthService
        health = await HealthService.full_health_check(self)
        logger.info("bot.health_check", **health)

        # 8-12. Load guild configurations, restore panels, validate resources
        for guild in self.guilds:
            await self.restoration_service.restore_guild_panel(guild)
            repaired = await self.team_creation_service.repair_guild_permissions(guild)
            logger.info("team.permissions_repaired", guild_id=guild.id, resources=repaired)

        logger.info("bot.startup.recovery_complete")

    async def on_guild_join(self, guild: discord.Guild):
        logger.info("guild.joined", guild_id=guild.id, name=guild.name)
        await self.setup_service.setup_guild(guild)

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info("guild.removed", guild_id=guild.id)

    async def close(self):
        logger.info("bot.shutdown.begin")
        await close_db()
        await super().close()
        logger.info("bot.shutdown.complete")


async def run_bot():
    bot = TeamManagementBot()
    await bot.start(settings.discord_token)
