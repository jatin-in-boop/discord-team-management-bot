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
from bot.services.invite_tracker_service import InviteTrackerService
from bot.services.server_log_service import ServerLogService
from bot.views.management_panel import ManagementPanelView

logger = get_logger(__name__)
settings = get_settings()


class TeamManagementBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        intents.invites = True
        intents.voice_states = True

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
        self.invite_tracker_service = InviteTrackerService(self)
        self.community_scheduler = CommunityScheduler(
            self, self.pulse_service, self.giveaway_service
        )
        self.permission_service = PermissionService()
        self.persistent_views_registered = False
        self.pulse_view_guild_ids: set[int] = set()
        self.pulse_presentation_guild_ids: set[int] = set()
        self.community_views_restored = False
        self.giveaway_views_restored = False
        ServerLogService.bind_bot(self)

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
            await self.invite_tracker_service.sync_guild(guild)
            await self.restoration_service.restore_guild_panel(guild)
            repaired = await self.team_creation_service.repair_guild_permissions(guild)
            logger.info("team.permissions_repaired", guild_id=guild.id, resources=repaired)
            first_view_registration = guild.id not in self.pulse_view_guild_ids
            if first_view_registration:
                from bot.views.community_systems import PulseMemberView

                self.add_view(PulseMemberView(self, guild))
                self.pulse_view_guild_ids.add(guild.id)
            if guild.id not in self.pulse_presentation_guild_ids:
                try:
                    created, failed = await self.pulse_service.apply_default_presentation(
                        guild, self.user.id if self.user else 0
                    )
                    self.pulse_presentation_guild_ids.add(guild.id)
                    logger.info(
                        "pulse.presentation_defaults_applied",
                        guild_id=guild.id,
                        manual_roles_created=created,
                        manual_role_warnings=failed,
                    )
                except Exception as exc:
                    logger.exception(
                        "pulse.presentation_defaults_failed",
                        guild_id=guild.id,
                        error=str(exc),
                    )
            try:
                refreshed = await self.pulse_service.refresh_leaderboard(
                    guild, force=first_view_registration
                )
                if refreshed:
                    logger.info(
                        "pulse.leaderboard_view_restored",
                        guild_id=guild.id,
                        forced=first_view_registration,
                    )
            except Exception as exc:
                logger.exception(
                    "pulse.leaderboard_view_restore_failed",
                    guild_id=guild.id,
                    error=str(exc),
                )
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
        await self.invite_tracker_service.sync_guild(guild)
        try:
            created, failed = await self.pulse_service.apply_default_presentation(
                guild, self.user.id if self.user else 0
            )
            self.pulse_presentation_guild_ids.add(guild.id)
            logger.info(
                "pulse.presentation_defaults_applied",
                guild_id=guild.id,
                manual_roles_created=created,
                manual_role_warnings=failed,
            )
        except Exception as exc:
            logger.exception(
                "pulse.presentation_defaults_failed",
                guild_id=guild.id,
                error=str(exc),
            )

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info("guild.removed", guild_id=guild.id)

    async def on_member_join(self, member: discord.Member):
        from bot.services.community_service import CommunityService

        event_key = f"join:{member.guild.id}:{member.id}:{member.joined_at.isoformat() if member.joined_at else 'unknown'}"
        await self.invite_tracker_service.attribute_join(member)
        await AuditService.log_action(
            member.guild.id,
            self.user.id if self.user else 0,
            "MEMBER_JOINED",
            {"member_id": member.id, "member_name": member.display_name},
        )
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
        await AuditService.log_action(
            member.guild.id,
            self.user.id if self.user else 0,
            "MEMBER_LEFT",
            {"member_id": member.id, "member_name": member.display_name},
        )
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

    async def _resolve_audit_actor(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        target_id: int | None = None,
    ) -> int:
        """Resolve the human actor from Discord's audit log when available."""
        fallback = self.user.id if self.user else 0
        try:
            if guild.me and not guild.me.guild_permissions.view_audit_log:
                return fallback
            now = discord.utils.utcnow()
            async for entry in guild.audit_logs(limit=8, action=action):
                if target_id and getattr(entry.target, "id", None) != target_id:
                    continue
                if entry.created_at and (now - entry.created_at).total_seconds() > 20:
                    continue
                return entry.user.id if entry.user else fallback
        except (discord.Forbidden, discord.HTTPException):
            pass
        return fallback

    async def on_invite_create(self, invite: discord.Invite):
        await self.invite_tracker_service.on_invite_create(invite)

    async def on_invite_delete(self, invite: discord.Invite):
        await self.invite_tracker_service.on_invite_delete(invite)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        actor_id = await self._resolve_audit_actor(
            channel.guild, discord.AuditLogAction.channel_create, channel.id
        )
        await AuditService.log_action(
            channel.guild.id,
            actor_id,
            "CHANNEL_CREATED",
            {"channel_id": channel.id, "channel_name": channel.name},
        )

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        actor_id = await self._resolve_audit_actor(
            channel.guild, discord.AuditLogAction.channel_delete, channel.id
        )
        await AuditService.log_action(
            channel.guild.id,
            actor_id,
            "CHANNEL_DELETED",
            {"channel_id": channel.id, "channel_name": channel.name},
        )

    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ):
        changes = []
        if before.name != after.name:
            changes.append(f"name: {before.name} → {after.name}")
        if before.category_id != after.category_id:
            changes.append("category changed")
        if changes:
            actor_id = await self._resolve_audit_actor(
                after.guild, discord.AuditLogAction.channel_update, after.id
            )
            await AuditService.log_action(
                after.guild.id,
                actor_id,
                "CHANNEL_UPDATED",
                {"channel_id": after.id, "channel_name": after.name, "changes": ", ".join(changes)},
            )

    async def on_guild_role_create(self, role: discord.Role):
        actor_id = await self._resolve_audit_actor(
            role.guild, discord.AuditLogAction.role_create, role.id
        )
        await AuditService.log_action(
            role.guild.id,
            actor_id,
            "ROLE_CREATED",
            {"role_id": role.id, "role_name": role.name},
        )

    async def on_guild_role_delete(self, role: discord.Role):
        actor_id = await self._resolve_audit_actor(
            role.guild, discord.AuditLogAction.role_delete, role.id
        )
        await AuditService.log_action(
            role.guild.id,
            actor_id,
            "ROLE_DELETED",
            {"role_id": role.id, "role_name": role.name},
        )

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(f"name: {before.name} → {after.name}")
        if before.color != after.color:
            changes.append("color changed")
        if before.hoist != after.hoist:
            changes.append("display position changed")
        if before.mentionable != after.mentionable:
            changes.append("mentionability changed")
        if changes:
            actor_id = await self._resolve_audit_actor(
                after.guild, discord.AuditLogAction.role_update, after.id
            )
            await AuditService.log_action(
                after.guild.id,
                actor_id,
                "ROLE_UPDATED",
                {"role_id": after.id, "role_name": after.name, "changes": ", ".join(changes)},
            )

    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        actor_id = await self._resolve_audit_actor(
            guild, discord.AuditLogAction.ban, user.id
        )
        await AuditService.log_action(
            guild.id,
            actor_id,
            "MEMBER_BANNED",
            {"member_id": user.id, "member_name": user.name},
        )

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        changes = []
        if before.nick != after.nick:
            changes.append("nickname changed")
        if before.communication_disabled_until != after.communication_disabled_until:
            changes.append("timeout changed")
        if changes:
            await AuditService.log_action(
                after.guild.id,
                self.user.id if self.user else 0,
                "MEMBER_UPDATED",
                {"member_id": after.id, "member_name": after.display_name, "changes": ", ".join(changes)},
            )
        if before.roles != after.roles:
            actor_id = await self._resolve_audit_actor(
                after.guild, discord.AuditLogAction.member_role_update, after.id
            )
            action = (
                "MEMBER_ROLES_UPDATED"
                if actor_id == (self.user.id if self.user else 0)
                else "MEMBER_ROLE_CHANGED"
            )
            await AuditService.log_action(
                after.guild.id,
                actor_id,
                action,
                {"member_id": after.id, "member_name": after.display_name},
            )

    async def on_message_delete(self, message: discord.Message):
        if message.guild and getattr(message.author, "bot", False) is False:
            await AuditService.log_action(
                message.guild.id,
                self.user.id if self.user else 0,
                "MESSAGE_DELETED",
                {"member_id": message.author.id, "channel_id": message.channel.id},
            )

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if (
            before.guild
            and getattr(before.author, "bot", False) is False
            and before.content != after.content
        ):
            await AuditService.log_action(
                before.guild.id,
                self.user.id if self.user else 0,
                "MESSAGE_EDITED",
                {"member_id": before.author.id, "channel_id": before.channel.id},
            )

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if before.channel == after.channel:
            return
        await AuditService.log_action(
            member.guild.id,
            self.user.id if self.user else 0,
            "VOICE_STATE_UPDATED",
            {
                "member_id": member.id,
                "channel_name": after.channel.name if after.channel else "left voice",
            },
        )

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        actor_id = await self._resolve_audit_actor(
            guild, discord.AuditLogAction.unban, user.id
        )
        await AuditService.log_action(
            guild.id,
            actor_id,
            "MEMBER_UNBANNED",
            {"member_id": user.id, "member_name": user.name},
        )

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.reaction_role_service.handle_reaction(payload, adding=True)
        await self.pulse_service.handle_reaction(payload)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.reaction_role_service.handle_reaction(payload, adding=False)

    async def on_message(self, message: discord.Message):
        await self.pulse_service.handle_message(message)
        if (
            message.guild
            and not message.author.bot
            and self.user
            and self.user in message.mentions
        ):
            from bot.services.mech_arena_service import MechArenaService
            from bot.views.mech_arena import answer_message

            guild_settings = await MechArenaService.ensure_guild_settings(message.guild.id)
            if guild_settings.enabled:
                question = message.content.replace(f"<@{self.user.id}>", "")
                question = question.replace(f"<@!{self.user.id}>", "").strip()
                if question:
                    await answer_message(message, question)
                    return
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
