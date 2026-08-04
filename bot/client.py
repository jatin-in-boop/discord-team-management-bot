import discord
from discord.ext import commands
from config.settings import get_settings
from app_logging.logger import get_logger
from database.engine import init_db, close_db
from bot.services.guild_setup import GuildSetupService
from bot.services.panel_restoration import PanelRestorationService
from bot.services.permission_service import PermissionService
from bot.services.team_creation import TeamCreationService
from bot.services.reaction_role_service import ReactionRoleService
from bot.services.audit_service import AuditService
from bot.services.pulse_service import PulseService
from bot.services.giveaway_service import GiveawayService
from bot.services.scheduler_service import CommunityScheduler
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
        self.reaction_role_service = ReactionRoleService(self)
        self.pulse_service = PulseService(self)
        self.giveaway_service = GiveawayService(self)
        self.community_scheduler = CommunityScheduler(
            self, self.pulse_service, self.giveaway_service
        )
        self.permission_service = PermissionService()
        self.persistent_views_registered = False
        self.community_views_restored = False
        self.giveaway_views_restored = False

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
        self.community_scheduler.start()
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
        if not self.community_views_restored:
            restored = await self.reaction_role_service.restore_views()
            self.community_views_restored = True
            logger.info("community.reaction_views_restored", count=restored)
        if not self.giveaway_views_restored:
            restored = await self.giveaway_service.restore_views()
            self.giveaway_views_restored = True
            logger.info("giveaway.views_restored", count=restored)
        await self.community_scheduler.tick()

        logger.info("bot.startup.recovery_complete")

    async def on_guild_join(self, guild: discord.Guild):
        logger.info("guild.joined", guild_id=guild.id, name=guild.name)
        await self.setup_service.setup_guild(guild)

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info("guild.removed", guild_id=guild.id)

    async def on_member_join(self, member: discord.Member):
        from bot.services.community_service import CommunityService

        event_key = f"join:{member.guild.id}:{member.id}:{member.joined_at.isoformat() if member.joined_at else 'unknown'}"
        if await CommunityService.event_already_logged(member.guild.id, "WELCOME_SENT", event_key):
            return
        ok, message = await CommunityService.send_configured_message(
            member.guild, member, "welcome"
        )
        if ok:
            await AuditService.log_action(
                member.guild.id,
                self.user.id if self.user else 0,
                "WELCOME_SENT",
                {"event_key": event_key, "member_id": member.id},
            )
        else:
            logger.info("community.welcome_skipped", guild_id=member.guild.id, reason=message)

    async def on_member_remove(self, member: discord.Member):
        from bot.services.community_service import CommunityService, departure_snapshot

        event_key = f"leave:{member.guild.id}:{member.id}:{member.joined_at.isoformat() if member.joined_at else 'unknown'}"
        if await CommunityService.event_already_logged(member.guild.id, "GOODBYE_SENT", event_key):
            return
        snapshot = departure_snapshot(member)
        ok, message = await CommunityService.send_configured_message(
            member.guild, snapshot, "goodbye"
        )
        if ok:
            await AuditService.log_action(
                member.guild.id,
                self.user.id if self.user else 0,
                "GOODBYE_SENT",
                {"event_key": event_key, "member_id": member.id},
            )
        else:
            logger.info("community.goodbye_skipped", guild_id=member.guild.id, reason=message)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.reaction_role_service.handle_reaction(payload, adding=True)
        await self.pulse_service.handle_reaction(payload)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.reaction_role_service.handle_reaction(payload, adding=False)

    async def on_message(self, message: discord.Message):
        await self.pulse_service.handle_message(message)
        await self.process_commands(message)

    async def close(self):
        logger.info("bot.shutdown.begin")
        await self.community_scheduler.stop()
        await close_db()
        await super().close()
        logger.info("bot.shutdown.complete")


async def run_bot():
    bot = TeamManagementBot()
    await bot.start(settings.discord_token)
