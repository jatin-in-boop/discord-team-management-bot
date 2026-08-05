from __future__ import annotations

from datetime import datetime

import discord
from sqlalchemy import select

from app_logging.logger import get_logger
from bot.services.audit_service import AuditService
from database.session import get_db_session
from models.models import CommunitySettings, InviteRecord

logger = get_logger(__name__)


class InviteTrackerService:
    def __init__(self, bot):
        self.bot = bot
        self.cache: dict[int, dict[str, int]] = {}

    async def sync_guild(self, guild: discord.Guild) -> int:
        try:
            invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.info("invite_tracker.sync_unavailable", guild_id=guild.id, error=str(exc))
            return 0
        self.cache[guild.id] = {invite.code: invite.uses or 0 for invite in invites}
        async with get_db_session() as session:
            for invite in invites:
                record = (
                    await session.execute(
                        select(InviteRecord).where(
                            InviteRecord.guild_id == guild.id,
                            InviteRecord.code == invite.code,
                        )
                    )
                ).scalar_one_or_none()
                if not record:
                    record = InviteRecord(guild_id=guild.id, code=invite.code)
                    session.add(record)
                record.inviter_id = invite.inviter.id if invite.inviter else None
                record.channel_id = invite.channel.id if invite.channel else None
                record.uses = invite.uses or 0
                record.max_uses = invite.max_uses
                record.max_age = invite.max_age
                record.temporary = invite.temporary
                record.last_seen_at = datetime.utcnow()
        return len(invites)

    async def on_invite_create(self, invite: discord.Invite) -> None:
        self.cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0
        await self._upsert(invite)
        await self._send_creation_notice(invite)
        await AuditService.log_action(
            invite.guild.id,
            invite.inviter.id if invite.inviter else (self.bot.user.id if self.bot.user else 0),
            "INVITE_CREATED",
            {
                "code": invite.code,
                "inviter_id": invite.inviter.id if invite.inviter else None,
                "channel_id": invite.channel.id if invite.channel else None,
            },
        )

    async def _send_creation_notice(self, invite: discord.Invite) -> None:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == invite.guild.id)
                )
            ).scalar_one_or_none()
        if not settings or not settings.invite_tracker_enabled or not settings.invite_tracker_channel_id:
            return
        channel = invite.guild.get_channel(settings.invite_tracker_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        creator = invite.inviter.mention if invite.inviter else "Unknown"
        destination = invite.channel.mention if invite.channel else "Unknown channel"
        embed = discord.Embed(
            title="Invite Created",
            description=f"Invite `{invite.code}` was created by {creator}.",
            color=0x5865F2,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Destination", value=destination)
        embed.add_field(name="Max uses", value=str(invite.max_uses or "Unlimited"))
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("invite_tracker.creation_notice_failed", guild_id=invite.guild.id, error=str(exc))

    async def on_invite_delete(self, invite: discord.Invite) -> None:
        self.cache.get(invite.guild.id, {}).pop(invite.code, None)
        await AuditService.log_action(
            invite.guild.id,
            self.bot.user.id if self.bot.user else 0,
            "INVITE_DELETED",
            {"code": invite.code, "channel_id": invite.channel.id if invite.channel else None},
        )

    async def attribute_join(self, member: discord.Member) -> discord.Invite | None:
        guild = member.guild
        previous = self.cache.get(guild.id, {})
        try:
            invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            return None
        used = next(
            (invite for invite in invites if (invite.uses or 0) > previous.get(invite.code, 0)),
            None,
        )
        self.cache[guild.id] = {invite.code: invite.uses or 0 for invite in invites}
        for invite in invites:
            await self._upsert(invite)
        if not used:
            return None

        inviter_id = used.inviter.id if used.inviter else None
        await AuditService.log_action(
            guild.id,
            inviter_id or (self.bot.user.id if self.bot.user else 0),
            "INVITE_USED",
            {
                "code": used.code,
                "inviter_id": inviter_id,
                "member_id": member.id,
                "uses": used.uses or 0,
            },
        )
        await self._send_join_notice(member, used)
        return used

    async def _upsert(self, invite: discord.Invite) -> None:
        async with get_db_session() as session:
            record = (
                await session.execute(
                    select(InviteRecord).where(
                        InviteRecord.guild_id == invite.guild.id,
                        InviteRecord.code == invite.code,
                    )
                )
            ).scalar_one_or_none()
            if not record:
                record = InviteRecord(guild_id=invite.guild.id, code=invite.code)
                session.add(record)
            record.inviter_id = invite.inviter.id if invite.inviter else None
            record.channel_id = invite.channel.id if invite.channel else None
            record.uses = invite.uses or 0
            record.max_uses = invite.max_uses
            record.max_age = invite.max_age
            record.temporary = invite.temporary
            record.last_seen_at = datetime.utcnow()

    async def _send_join_notice(self, member: discord.Member, invite: discord.Invite) -> None:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == member.guild.id)
                )
            ).scalar_one_or_none()
        if not settings or not settings.invite_tracker_enabled or not settings.invite_tracker_channel_id:
            return
        channel = member.guild.get_channel(settings.invite_tracker_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        inviter = invite.inviter.mention if invite.inviter else "Unknown / vanity invite"
        embed = discord.Embed(
            title="Invite Used",
            description=f"{member.mention} joined using invite `{invite.code}`.",
            color=0x57F287,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Invited by", value=inviter)
        embed.add_field(name="Invite uses", value=str(invite.uses or 0))
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("invite_tracker.notice_failed", guild_id=member.guild.id, error=str(exc))