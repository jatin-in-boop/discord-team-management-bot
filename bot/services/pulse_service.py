from __future__ import annotations

import math
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import discord
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app_logging.logger import get_logger
from bot.services.audit_service import AuditService
from bot.services.community_service import CommunityService
from database.session import get_db_session
from models.models import (
    Guild,
    ManagedRoleOwnerType,
    ManagedRoleRegistry,
    PulseMember,
    PulsePacing,
    PulseReward,
    PulseSettings,
    RoleSource,
    XPLedger,
    XPSource,
)

logger = get_logger(__name__)

PACE_MULTIPLIER = {
    PulsePacing.RELAXED: 0.80,
    PulsePacing.BALANCED: 1.00,
    PulsePacing.AMBITIOUS: 1.25,
}
DEFAULT_BANDS = [
    {"key": "new_signal", "name": "New Signal", "min": 1, "max": 4, "color": 0x64748B},
    {"key": "active_presence", "name": "Active Presence", "min": 5, "max": 9, "color": 0x22D3EE},
    {"key": "familiar_voice", "name": "Familiar Voice", "min": 10, "max": 19, "color": 0x8B5CF6},
    {"key": "community_pillar", "name": "Community Pillar", "min": 20, "max": 34, "color": 0xF59E0B},
    {"key": "trusted_core", "name": "Trusted Core", "min": 35, "max": 49, "color": 0xFB7185},
    {"key": "guild_beacon", "name": "Guild Beacon", "min": 50, "max": 74, "color": 0xFACC15},
    {"key": "inner_circle", "name": "Inner Circle", "min": 75, "max": 99, "color": 0xA78BFA},
    {"key": "legacy_signal", "name": "Legacy Signal", "min": 100, "max": 1000000, "color": 0xE2E8F0},
]


def xp_required(level: int, pacing: PulsePacing = PulsePacing.BALANCED) -> int:
    return max(1, round(100 * level ** 1.55 * PACE_MULTIPLIER[pacing]))


def level_for_xp(total_xp: int, pacing: PulsePacing, maximum: int = 100) -> int:
    level = 1
    while level < maximum and total_xp >= xp_required(level, pacing):
        level += 1
    return level


def progress_for(total_xp: int, level: int, pacing: PulsePacing) -> tuple[int, int]:
    previous = 0 if level <= 1 else xp_required(level - 1, pacing)
    current = xp_required(level, pacing)
    return max(0, total_xp - previous), max(1, current - previous)


def band_for_level(level: int, bands: list[dict]) -> dict:
    for band in bands:
        if int(band.get("min", 1)) <= level <= int(band.get("max", 1000000)):
            return band
    return bands[-1]


class PulseService:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def get_or_create_settings(guild: discord.Guild) -> PulseSettings:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings:
                settings = PulseSettings(
                    guild_id=guild.id,
                    band_config=DEFAULT_BANDS,
                    source_config={
                        "message": {"amount": 8, "cooldown": 60, "daily_cap": 600, "min_length": 12},
                        "voice": {"amount": 6, "block_seconds": 300, "daily_cap": 480},
                        "reaction": {"amount": 1, "daily_cap": 50},
                        "event": {"amount": 25},
                    },
                )
                session.add(settings)
                await session.flush()
            return settings

    async def configure(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        *,
        enabled: Optional[bool] = None,
        pacing: Optional[PulsePacing] = None,
        sources: Optional[list[str]] = None,
        display_name: Optional[str] = None,
    ) -> PulseSettings:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings:
                settings = PulseSettings(guild_id=guild.id, band_config=DEFAULT_BANDS)
                session.add(settings)
            if enabled is not None:
                settings.enabled = enabled
            if pacing is not None:
                settings.pacing = pacing
            if sources is not None:
                settings.enabled_sources = sources
            if display_name is not None:
                settings.display_name = display_name[:50]
            settings.updated_by = executor.id
            await session.flush()
        await AuditService.log_action(
            guild.id, executor.id, "PULSE_CONFIG_UPDATED",
            {"enabled": enabled, "pacing": pacing.value if pacing else None, "sources": sources},
        )
        return await self.get_or_create_settings(guild)

    async def set_leaderboard_channel(
        self, guild: discord.Guild, executor: discord.Member, channel_id: int
    ) -> bool:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings:
                settings = PulseSettings(guild_id=guild.id, band_config=DEFAULT_BANDS)
                session.add(settings)
            settings.leaderboard_channel_id = channel_id
            settings.updated_by = executor.id
            await session.commit()
        await AuditService.log_action(
            guild.id, executor.id, "PULSE_LEADERBOARD_CHANNEL_UPDATED",
            {"channel_id": channel_id},
        )
        return True

    async def get_member(self, guild_id: int, member_id: int) -> Optional[PulseMember]:
        async with get_db_session() as session:
            return (
                await session.execute(
                    select(PulseMember).where(
                        PulseMember.guild_id == guild_id,
                        PulseMember.member_id == member_id,
                    )
                )
            ).scalar_one_or_none()

    async def award_xp(
        self,
        guild: discord.Guild,
        member: discord.Member,
        amount: int,
        source: XPSource,
        idempotency_key: str,
        *,
        reason: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> tuple[bool, str, Optional[PulseMember]]:
        if amount == 0 or member.bot:
            return False, "XP award skipped.", None
        settings = await self.get_or_create_settings(guild)
        if source != XPSource.MANUAL and (
            not settings.enabled or source.value not in (settings.enabled_sources or [])
        ):
            return False, "XP source is disabled.", None
        async with get_db_session() as session:
            existing = (
                await session.execute(
                    select(XPLedger).where(XPLedger.idempotency_key == idempotency_key)
                )
            ).scalar_one_or_none()
            if existing:
                return False, "Duplicate XP event ignored.", None
            pulse_member = (
                await session.execute(
                    select(PulseMember).where(
                        PulseMember.guild_id == guild.id,
                        PulseMember.member_id == member.id,
                    )
                )
            ).scalar_one_or_none()
            if not pulse_member:
                pulse_member = PulseMember(guild_id=guild.id, member_id=member.id)
                session.add(pulse_member)
                await session.flush()
            old_level = pulse_member.current_level
            pulse_member.total_xp = max(0, pulse_member.total_xp + amount)
            if amount > 0:
                pulse_member.current_season_xp += amount
            pulse_member.current_level = level_for_xp(
                pulse_member.total_xp, settings.pacing, settings.max_level
            )
            pulse_member.last_activity_at = datetime.utcnow()
            session.add(
                XPLedger(
                    guild_id=guild.id,
                    member_id=member.id,
                    pulse_member_id=pulse_member.id,
                    amount=amount,
                    source=source,
                    source_reference=source_reference,
                    idempotency_key=idempotency_key,
                    reason=reason,
                )
            )
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                return False, "Duplicate XP event ignored.", None
            new_level = pulse_member.current_level
        if new_level != old_level:
            await self.apply_band_role(guild, member, new_level, settings)
            await AuditService.log_action(
                guild.id, self.bot.user.id if self.bot.user else 0,
                "PULSE_LEVEL_UP",
                {"member_id": member.id, "from": old_level, "to": new_level},
            )
        return True, f"+{amount} XP awarded.", await self.get_member(guild.id, member.id)

    async def handle_message(self, message: discord.Message) -> None:
        if not message.guild or not isinstance(message.author, discord.Member) or message.author.bot:
            return
        settings = await self.get_or_create_settings(message.guild)
        config = (settings.source_config or {}).get("message", {})
        content = (message.content or "").strip()
        if len(content) < int(config.get("min_length", 12)):
            return
        if content.startswith("<@") and len(content.split()) <= 2:
            return
        cooldown = int(config.get("cooldown", 60))
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_cap = int(config.get("daily_cap", 600))
        async with get_db_session() as session:
            recent = (
                await session.execute(
                    select(XPLedger).where(
                        XPLedger.guild_id == message.guild.id,
                        XPLedger.member_id == message.author.id,
                        XPLedger.source == XPSource.MESSAGE,
                        XPLedger.created_at >= datetime.utcnow() - timedelta(seconds=cooldown),
                    ).order_by(XPLedger.created_at.desc()).limit(1)
                )
            ).scalar_one_or_none()
            daily_total = (
                await session.execute(
                    select(func.coalesce(func.sum(XPLedger.amount), 0)).where(
                        XPLedger.guild_id == message.guild.id,
                        XPLedger.member_id == message.author.id,
                        XPLedger.source == XPSource.MESSAGE,
                        XPLedger.created_at >= day_start,
                    )
                )
            ).scalar_one()
            fingerprint = hashlib.sha256(" ".join(content.lower().split()).encode()).hexdigest()
            repeated = (
                await session.execute(
                    select(XPLedger).where(
                        XPLedger.guild_id == message.guild.id,
                        XPLedger.member_id == message.author.id,
                        XPLedger.source == XPSource.MESSAGE,
                        XPLedger.reason == f"fingerprint:{fingerprint}",
                        XPLedger.created_at >= datetime.utcnow() - timedelta(hours=24),
                    ).limit(1)
                )
            ).scalar_one_or_none()
        if recent or int(daily_total or 0) >= daily_cap or repeated:
            return
        await self.award_xp(
            message.guild, message.author, int(config.get("amount", 8)),
            XPSource.MESSAGE, f"message:{message.id}", source_reference=str(message.id),
            reason=f"fingerprint:{fingerprint}",
        )

    async def handle_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id or not payload.member or payload.member.bot:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        settings = await self.get_or_create_settings(guild)
        config = (settings.source_config or {}).get("reaction", {})
        allowed = config.get("emoji_allowlist") or []
        emoji = str(payload.emoji)
        if allowed and emoji not in allowed:
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        if message.author.id == payload.user_id or message.author.bot:
            return
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        async with get_db_session() as session:
            daily_total = (
                await session.execute(
                    select(func.coalesce(func.sum(XPLedger.amount), 0)).where(
                        XPLedger.guild_id == guild.id,
                        XPLedger.member_id == payload.user_id,
                        XPLedger.source == XPSource.REACTION,
                        XPLedger.created_at >= day_start,
                    )
                )
            ).scalar_one()
        if int(daily_total or 0) >= int(config.get("daily_cap", 50)):
            return
        await self.award_xp(
            guild,
            payload.member,
            int(config.get("amount", 1)),
            XPSource.REACTION,
            f"reaction:{payload.message_id}:{payload.user_id}:{emoji}",
            source_reference=str(payload.message_id),
        )

    async def award_voice_blocks(self, guild: discord.Guild) -> int:
        settings = await self.get_or_create_settings(guild)
        config = (settings.source_config or {}).get("voice", {})
        eligible_channels = {int(item) for item in config.get("channel_ids", [])}
        awarded = 0
        for channel in guild.voice_channels:
            if eligible_channels and channel.id not in eligible_channels:
                continue
            if channel.id == guild.afk_channel_id:
                continue
            members = [item for item in channel.members if not item.bot]
            if not config.get("allow_solo", False) and len(members) < 2:
                continue
            for member in members:
                if member.voice and (
                    member.voice.self_deaf or member.voice.deaf
                ):
                    continue
                bucket = int(datetime.utcnow().timestamp()) // int(
                    config.get("block_seconds", 300)
                )
                ok, _, _ = await self.award_xp(
                    guild,
                    member,
                    int(config.get("amount", 6)),
                    XPSource.VOICE,
                    f"voice:{member.id}:{bucket}",
                )
                awarded += int(ok)
        return awarded

    async def profile(self, guild: discord.Guild, member: discord.Member) -> dict:
        settings = await self.get_or_create_settings(guild)
        data = await self.get_member(guild.id, member.id)
        total = data.total_xp if data else 0
        level = level_for_xp(total, settings.pacing, settings.max_level)
        current, needed = progress_for(total, level, settings.pacing)
        async with get_db_session() as session:
            rank = (
                await session.execute(
                    select(func.count(PulseMember.id)).where(
                        PulseMember.guild_id == guild.id,
                        PulseMember.total_xp > total,
                    )
                )
            ).scalar_one() + 1
            seven_days = (
                await session.execute(
                    select(func.coalesce(func.sum(XPLedger.amount), 0)).where(
                        XPLedger.guild_id == guild.id,
                        XPLedger.member_id == member.id,
                        XPLedger.created_at >= datetime.utcnow() - timedelta(days=7),
                    )
                )
            ).scalar_one()
        return {
            "settings": settings, "member": data, "total": total, "level": level,
            "current": current, "needed": needed, "rank": rank, "seven_days": seven_days,
            "band": band_for_level(level, settings.band_config or DEFAULT_BANDS),
        }

    async def leaderboard(self, guild: discord.Guild, limit: int = 10) -> list[PulseMember]:
        async with get_db_session() as session:
            return list(
                (
                    await session.execute(
                        select(PulseMember).where(
                            PulseMember.guild_id == guild.id
                        ).order_by(
                            PulseMember.total_xp.desc(),
                            PulseMember.current_level.desc(),
                            PulseMember.created_at.asc(),
                            PulseMember.member_id.asc(),
                        ).limit(limit)
                    )
                ).scalars().all()
            )

    async def refresh_leaderboard(self, guild: discord.Guild) -> bool:
        """Refresh the configured leaderboard message in place, if configured."""
        from bot.views.community_systems import leaderboard_embed

        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings or not settings.enabled or not settings.leaderboard_channel_id:
                return False
            now = datetime.utcnow()
            if (
                settings.leaderboard_last_success_at
                and (now - settings.leaderboard_last_success_at).total_seconds()
                < settings.leaderboard_refresh_interval
            ):
                return False
            settings.leaderboard_last_attempt_at = now
            channel_id = settings.leaderboard_channel_id
            message_id = settings.leaderboard_message_id
            await session.commit()

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False
        embed = await leaderboard_embed(guild, self.bot)
        rendered = str(embed.to_dict())
        try:
            message = None
            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                except discord.NotFound:
                    pass
            if message:
                if rendered == settings.leaderboard_rendered:
                    async with get_db_session() as session:
                        current = (
                            await session.execute(
                                select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                            )
                        ).scalar_one_or_none()
                        if current:
                            current.leaderboard_last_success_at = datetime.utcnow()
                            await session.commit()
                    return True
                from bot.views.community_systems import PulseMemberView
                await message.edit(embed=embed, view=PulseMemberView(self.bot, guild))
            else:
                from bot.views.community_systems import PulseMemberView
                message = await channel.send(
                    embed=embed, view=PulseMemberView(self.bot, guild)
                )
            async with get_db_session() as session:
                current = (
                    await session.execute(
                        select(PulseSettings).where(PulseSettings.guild_id == guild.id)
                    )
                ).scalar_one_or_none()
                if current:
                    current.leaderboard_message_id = message.id
                    current.leaderboard_rendered = rendered
                    current.leaderboard_last_success_at = datetime.utcnow()
                    await session.commit()
            return True
        except (discord.Forbidden, discord.HTTPException):
            logger.warning("pulse.leaderboard_refresh_failed", guild_id=guild.id)
            return False

    async def apply_band_role(
        self, guild: discord.Guild, member: discord.Member, level: int, settings: PulseSettings
    ) -> None:
        band = band_for_level(level, settings.band_config or DEFAULT_BANDS)
        async with get_db_session() as session:
            rewards = list(
                (
                    await session.execute(
                        select(PulseReward).where(
                            PulseReward.guild_id == guild.id,
                            PulseReward.kind == "band",
                            PulseReward.enabled.is_(True),
                        )
                    )
                ).scalars().all()
            )
        target = next((r for r in rewards if r.band_key == band.get("key")), None)
        if not target:
            return
        role = guild.get_role(target.role_id)
        if not role:
            return
        valid, error = await CommunityService.validate_role(guild, role)
        if not valid:
            logger.warning("pulse.band_role_unmanageable", guild_id=guild.id, reason=error)
            return
        try:
            if role not in member.roles:
                await member.add_roles(role, reason="Guild Pulse band transition")
            old_roles = [
                r for r in member.roles
                if r.id != role.id and any(x.role_id == r.id for x in rewards)
            ]
            if old_roles:
                await member.remove_roles(*old_roles, reason="Guild Pulse band transition")
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("pulse.band_transition_failed", guild_id=guild.id, error=str(exc))

    async def ensure_band_roles(self, guild: discord.Guild, executor_id: int = 0) -> tuple[int, int]:
        """Create missing bot-owned band roles and synchronize existing ones."""
        settings = await self.get_or_create_settings(guild)
        created = failed = 0
        async with get_db_session() as session:
            rewards = list(
                (
                    await session.execute(
                        select(PulseReward).where(
                            PulseReward.guild_id == guild.id,
                            PulseReward.kind == "band",
                        )
                    )
                ).scalars().all()
            )
        for band in settings.band_config or DEFAULT_BANDS:
            reward = next((item for item in rewards if item.band_key == band.get("key")), None)
            if reward and guild.get_role(reward.role_id):
                continue
            if reward and not guild.get_role(reward.role_id):
                failed += 1
                continue
            config = {
                "role_name": band.get("name", "Pulse Band"),
                "brand_tag": (settings.brand_config or {}).get("short_tag", "Pulse"),
                "symbol": (settings.brand_config or {}).get("symbol", "◈"),
            }
            name = _format_role_name(config["role_name"], config["brand_tag"], config["symbol"])
            try:
                role = await guild.create_role(
                    name=name,
                    colour=discord.Colour(int(band.get("color", 0x5865F2))),
                    hoist=False,
                    mentionable=False,
                    reason="Create Guild Pulse managed band role",
                )
                async with get_db_session() as session:
                    reward = PulseReward(
                        guild_id=guild.id,
                        kind="band",
                        threshold=int(band.get("min", 1)),
                        band_key=band.get("key"),
                        role_id=role.id,
                        role_source=RoleSource.BOT_CREATED,
                        brand_config=config,
                        mutually_exclusive_group="guild_pulse_bands",
                        enabled=True,
                        created_by=executor_id,
                    )
                    session.add(reward)
                    await session.flush()
                    reward_id = reward.id
                await CommunityService.register_managed_role(
                    guild.id,
                    role,
                    reward_id,
                    ManagedRoleOwnerType.PULSE_BAND,
                    config,
                    "Guild Pulse band role",
                )
                created += 1
            except (discord.Forbidden, discord.HTTPException, ValueError):
                failed += 1
        await self.sync_band_roles(guild)
        return created, failed

    async def sync_band_roles(self, guild: discord.Guild) -> tuple[int, int]:
        settings = await self.get_or_create_settings(guild)
        synced = failed = 0
        async with get_db_session() as session:
            rewards = list(
                (
                    await session.execute(
                        select(PulseReward).where(
                            PulseReward.guild_id == guild.id,
                            PulseReward.kind == "band",
                        )
                    )
                ).scalars().all()
            )
        for reward in rewards:
            role = guild.get_role(reward.role_id)
            if not role:
                failed += 1
                continue
            band = next(
                (item for item in settings.band_config if item.get("key") == reward.band_key),
                {},
            )
            config = reward.brand_config or {}
            desired = _format_role_name(
                config.get("role_name") or band.get("name", "Pulse Band"),
                config.get("brand_tag", (settings.brand_config or {}).get("short_tag", "Pulse")),
                config.get("symbol", (settings.brand_config or {}).get("symbol", "◈")),
            )
            try:
                valid, error = await CommunityService.validate_role(guild, role)
                if not valid:
                    raise ValueError(error)
                changes = {"name": desired}
                if band.get("color") is not None:
                    changes["colour"] = discord.Colour(int(band["color"]))
                await role.edit(**changes, reason="Synchronize Guild Pulse band role")
                async with get_db_session() as session:
                    registry = (
                        await session.execute(
                            select(ManagedRoleRegistry).where(
                                ManagedRoleRegistry.discord_role_id == role.id,
                                ManagedRoleRegistry.owner_type == ManagedRoleOwnerType.PULSE_BAND,
                            )
                        )
                    ).scalar_one_or_none()
                    if registry:
                        registry.generated_name = desired
                        registry.color = role.color.value
                        registry.brand_tag = config.get("brand_tag")
                        registry.symbol = config.get("symbol")
                        registry.last_sync_status = "synced"
                        registry.last_sync_error = None
                        await session.commit()
                synced += 1
            except (ValueError, discord.HTTPException, discord.Forbidden):
                failed += 1
        return synced, failed


def _format_role_name(name: str, tag: str, symbol: str) -> str:
    result = f"{symbol} {tag} {name}".strip()
    result = result.replace("@everyone", "everyone").replace("@here", "here")
    return result[:100]