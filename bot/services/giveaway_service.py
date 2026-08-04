from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import discord
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app_logging.logger import get_logger
from bot.services.audit_service import AuditService
from database.session import get_db_session
from models.models import (
    ClaimStatus,
    Giveaway,
    GiveawayDraw,
    GiveawayEntry,
    GiveawayEntryMode,
    GiveawayStatus,
    GiveawayWinner,
)

logger = get_logger(__name__)


class GiveawayService:
    def __init__(self, bot):
        self.bot = bot

    async def create(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        *,
        channel_id: int,
        title: str,
        prize_description: str,
        start_at: datetime,
        end_at: datetime,
        winner_count: int = 1,
        claim_window_seconds: int = 86400,
        eligibility: Optional[dict] = None,
        presentation: Optional[dict] = None,
        acknowledge_prize_responsibility: bool = False,
    ) -> tuple[bool, str, Optional[int]]:
        if end_at <= start_at:
            return False, "The end time must be after the start time.", None
        if winner_count < 1 or winner_count > 50:
            return False, "Winner count must be between 1 and 50.", None
        if not acknowledge_prize_responsibility:
            return False, "Acknowledge that the organizer is responsible for prize fulfillment.", None
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False, "Choose a valid text channel.", None
        status = GiveawayStatus.LIVE if start_at <= datetime.utcnow() else GiveawayStatus.SCHEDULED
        async with get_db_session() as session:
            giveaway = Giveaway(
                guild_id=guild.id, channel_id=channel_id, title=title[:256],
                prize_description=prize_description[:4000], organizer_id=executor.id,
                status=status, start_at=start_at, end_at=end_at,
                winner_count=winner_count, claim_window_seconds=max(60, claim_window_seconds),
                eligibility_config=eligibility or {}, presentation_config=presentation or {},
                organizer_acknowledged=True, created_by=executor.id,
            )
            session.add(giveaway)
            await session.flush()
            giveaway_id = giveaway.id
        await AuditService.log_action(
            guild.id, executor.id, "GIVEAWAY_CREATED",
            {"giveaway_id": giveaway_id, "title": title, "status": status.value},
        )
        if status == GiveawayStatus.LIVE:
            await self.publish(guild, giveaway_id)
        return True, "Giveaway created.", giveaway_id

    async def get(self, giveaway_id: int) -> Optional[Giveaway]:
        async with get_db_session() as session:
            return (
                await session.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
            ).scalar_one_or_none()

    async def render(self, giveaway: Giveaway, *, entries: Optional[int] = None) -> discord.Embed:
        config = giveaway.presentation_config or {}
        embed = discord.Embed(
            title=f"🎁 {config.get('title') or giveaway.title}",
            description=(
                f"{giveaway.prize_description}\n\n"
                f"🏆 Winners: **{giveaway.winner_count}**\n"
                f"⏱ Ends <t:{int(giveaway.end_at.timestamp())}:R> · "
                f"<t:{int(giveaway.end_at.timestamp())}:F>\n\n"
                "The bot conducts the draw only. The organizer is responsible "
                "for providing and delivering the prize."
            ),
            color=int(config.get("color", 0xF59E0B)),
        )
        if entries is not None:
            embed.add_field(name="🎟 Entries", value=str(entries), inline=True)
        embed.set_footer(text="Giveaway Operations · Rules available below")
        return embed

    async def publish(self, guild: discord.Guild, giveaway_id: int) -> tuple[bool, str]:
        from bot.views.giveaways import GiveawayMemberView

        giveaway = await self.get(giveaway_id)
        if not giveaway or giveaway.guild_id != guild.id:
            return False, "Giveaway not found."
        channel = guild.get_channel(giveaway.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False, "The giveaway channel is unavailable."
        async with get_db_session() as session:
            count = (
                await session.execute(
                    select(GiveawayEntry).where(GiveawayEntry.giveaway_id == giveaway_id)
                )
            ).scalars().all()
        embed = await self.render(giveaway, entries=len(count))
        try:
            message = None
            if giveaway.message_id:
                try:
                    message = await channel.fetch_message(giveaway.message_id)
                except discord.NotFound:
                    pass
            if message:
                await message.edit(embed=embed, view=GiveawayMemberView(self.bot, giveaway_id))
            else:
                message = await channel.send(
                    embed=embed, view=GiveawayMemberView(self.bot, giveaway_id)
                )
            async with get_db_session() as session:
                db = await session.get(Giveaway, giveaway_id)
                if db:
                    db.message_id = message.id
                    db.status = GiveawayStatus.LIVE
                    await session.commit()
            return True, "Giveaway published."
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("giveaway.publish_failed", error=str(exc))
            return False, "Discord could not publish the giveaway."

    async def check_eligibility(self, giveaway: Giveaway, member: discord.Member) -> tuple[bool, str]:
        if member.bot:
            return False, "Bots cannot enter giveaways."
        rules = giveaway.eligibility_config or {}
        account_age = rules.get("minimum_account_age_days")
        if account_age and (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days < int(account_age):
            return False, f"Your Discord account must be at least {account_age} days old."
        membership_age = rules.get("minimum_membership_age_days")
        if membership_age and member.joined_at:
            joined = member.joined_at.replace(tzinfo=None)
            if (datetime.utcnow() - joined).days < int(membership_age):
                return False, f"You must be in the server for at least {membership_age} days."
        excluded = {int(role_id) for role_id in rules.get("excluded_role_ids", [])}
        if excluded.intersection(role.id for role in member.roles):
            return False, "One of your roles is excluded from this giveaway."
        required = {int(role_id) for role_id in rules.get("required_role_ids", [])}
        if required and not required.intersection(role.id for role in member.roles):
            return False, "You do not have a required giveaway role."
        required_level = rules.get("required_pulse_level")
        if required_level:
            from bot.services.pulse_service import PulseService
            profile = await PulseService(self.bot).profile(member.guild, member)
            if profile["level"] < int(required_level):
                return False, f"You need Pulse Level {required_level} to enter."
        return True, ""

    async def enter(self, guild: discord.Guild, member: discord.Member, giveaway_id: int) -> tuple[bool, str]:
        giveaway = await self.get(giveaway_id)
        if not giveaway or giveaway.guild_id != guild.id:
            return False, "Giveaway not found."
        if giveaway.status != GiveawayStatus.LIVE or datetime.utcnow() >= giveaway.end_at:
            return False, "This giveaway has ended or is not live."
        eligible, reason = await self.check_eligibility(giveaway, member)
        if not eligible:
            return False, reason
        async with get_db_session() as session:
            existing = (
                await session.execute(
                    select(GiveawayEntry).where(
                        GiveawayEntry.giveaway_id == giveaway_id,
                        GiveawayEntry.member_id == member.id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return False, "You are already entered."
            session.add(
                GiveawayEntry(
                    giveaway_id=giveaway_id, guild_id=guild.id,
                    member_id=member.id, entered_at=datetime.utcnow(),
                    last_revalidated_at=datetime.utcnow(),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False, "You are already entered."
        return True, "Entry confirmed."

    async def end(self, guild: discord.Guild, giveaway_id: int, actor_id: int = 0, reason: str = "scheduled_end") -> tuple[bool, str]:
        async with get_db_session() as session:
            db = (
                await session.execute(
                    select(Giveaway).where(
                        Giveaway.id == giveaway_id,
                        Giveaway.guild_id == guild.id,
                    ).with_for_update()
                )
            ).scalar_one_or_none()
            if not db:
                return False, "Giveaway not found."
            if db.status not in (GiveawayStatus.SCHEDULED, GiveawayStatus.LIVE):
                return False, "Giveaway is already closed or being finalized."
            db.status = GiveawayStatus.ENDING
            entries = list(
                (
                    await session.execute(
                        select(GiveawayEntry).where(
                            GiveawayEntry.giveaway_id == giveaway_id,
                            GiveawayEntry.eligibility_status == "eligible",
                        )
                    )
                ).scalars().all()
            )
            eligible = []
            guild_member = {m.id: m for m in guild.members}
            for entry in entries:
                member = guild_member.get(entry.member_id)
                if member:
                    ok, failure = await self.check_eligibility(db, member)
                    entry.last_revalidated_at = datetime.utcnow()
                    entry.eligibility_status = "eligible" if ok else "ineligible"
                    entry.eligibility_failure_reason = failure or None
                    if ok:
                        eligible.append(entry)
            if not eligible:
                db.status = GiveawayStatus.COMPLETED
                await session.commit()
                return False, "No eligible entries remained."
            seed = secrets.token_hex(32)
            seed_hash = hashlib.sha256(seed.encode()).hexdigest()
            ordered = sorted(eligible, key=lambda item: item.id)
            ranked = sorted(
                ordered,
                key=lambda item: hashlib.sha256(f"{seed}:{item.id}".encode()).hexdigest(),
            )
            winners = ranked[: min(db.winner_count, len(ranked))]
            draw = GiveawayDraw(
                giveaway_id=giveaway_id,
                draw_number=(await session.execute(
                    select(GiveawayDraw).where(GiveawayDraw.giveaway_id == giveaway_id)
                )).scalars().all().__len__() + 1,
                eligible_entry_count=len(eligible),
                winner_order=[item.member_id for item in winners],
                seed_hash=seed_hash,
                reveal_seed=seed,
                reason=reason,
                created_by=actor_id,
            )
            session.add(draw)
            await session.flush()
            deadline = datetime.utcnow() + timedelta(seconds=db.claim_window_seconds)
            for position, entry in enumerate(winners, 1):
                session.add(
                    GiveawayWinner(
                        draw_id=draw.id, giveaway_id=giveaway_id,
                        member_id=entry.member_id, position=position,
                        claim_deadline=deadline,
                    )
                )
            db.status = GiveawayStatus.WINNER_PENDING_CLAIM
            await session.commit()
        await self._announce_winners(guild, giveaway_id, winners, deadline)
        return True, "Giveaway ended and winners selected."

    async def _announce_winners(
        self, guild: discord.Guild, giveaway_id: int, winners: list, deadline: datetime
    ) -> None:
        from bot.views.giveaways import GiveawayMemberView

        giveaway = await self.get(giveaway_id)
        if not giveaway:
            return
        channel = guild.get_channel(giveaway.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        mentions = "\n".join(
            f"{position}. <@{entry.member_id}>"
            for position, entry in enumerate(winners, 1)
        )
        embed = discord.Embed(
            title="🎉 Giveaway Complete",
            description=(
                f"**{giveaway.title}**\n\n{mentions}\n\n"
                f"Winners must claim by <t:{int(deadline.timestamp())}:F>.\n"
                "The organizer is responsible for providing and delivering the prize."
            ),
            color=0x57F287,
        )
        try:
            message = None
            if giveaway.message_id:
                try:
                    message = await channel.fetch_message(giveaway.message_id)
                except discord.NotFound:
                    pass
            if message:
                await message.edit(
                    embed=embed,
                    view=GiveawayMemberView(self.bot, giveaway_id),
                )
            else:
                await channel.send(embed=embed, view=GiveawayMemberView(self.bot, giveaway_id))
        except (discord.Forbidden, discord.HTTPException):
            logger.warning("giveaway.winner_announcement_failed", giveaway_id=giveaway_id)

    async def pause_or_resume(
        self, guild: discord.Guild, giveaway_id: int, actor_id: int
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            giveaway = (
                await session.execute(
                    select(Giveaway).where(
                        Giveaway.id == giveaway_id,
                        Giveaway.guild_id == guild.id,
                    ).with_for_update()
                )
            ).scalar_one_or_none()
            if not giveaway:
                return False, "Giveaway not found."
            if giveaway.status == GiveawayStatus.LIVE:
                giveaway.status = GiveawayStatus.PAUSED
                message = "Giveaway entries paused."
            elif giveaway.status == GiveawayStatus.PAUSED:
                giveaway.status = GiveawayStatus.LIVE
                message = "Giveaway entries resumed."
            else:
                return False, "Only a live or paused giveaway can be changed."
            await session.commit()
        await AuditService.log_action(
            guild.id, actor_id, "GIVEAWAY_STATE_CHANGED",
            {"giveaway_id": giveaway_id, "status": giveaway.status.value},
        )
        return True, message

    async def cancel(
        self, guild: discord.Guild, giveaway_id: int, actor_id: int, reason: str
    ) -> tuple[bool, str]:
        reason = reason.strip()[:500]
        if not reason:
            return False, "A cancellation reason is required."
        async with get_db_session() as session:
            giveaway = (
                await session.execute(
                    select(Giveaway).where(
                        Giveaway.id == giveaway_id,
                        Giveaway.guild_id == guild.id,
                    ).with_for_update()
                )
            ).scalar_one_or_none()
            if not giveaway:
                return False, "Giveaway not found."
            if giveaway.status in (
                GiveawayStatus.COMPLETED,
                GiveawayStatus.CANCELLED,
            ):
                return False, "This giveaway is already closed."
            giveaway.status = GiveawayStatus.CANCELLED
            giveaway.cancelled_reason = reason
            channel_id = giveaway.channel_id
            message_id = giveaway.message_id
            await session.commit()
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel) and message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(
                    embed=discord.Embed(
                        title="🛑 Giveaway Cancelled",
                        description=(
                            f"**{giveaway.title}**\n\n{reason}\n\n"
                            "No prize has been distributed by the bot."
                        ),
                        color=0xED4245,
                    ),
                    view=None,
                )
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning("giveaway.cancel_message_update_failed", giveaway_id=giveaway_id)
        await AuditService.log_action(
            guild.id, actor_id, "GIVEAWAY_CANCELLED",
            {"giveaway_id": giveaway_id, "reason": reason},
        )
        return True, "Giveaway cancelled."

    async def reroll(
        self, guild: discord.Guild, giveaway_id: int, actor_id: int, reason: str
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            giveaway = (
                await session.execute(
                    select(Giveaway).where(
                        Giveaway.id == giveaway_id,
                        Giveaway.guild_id == guild.id,
                    ).with_for_update()
                )
            ).scalar_one_or_none()
            if not giveaway:
                return False, "Giveaway not found."
            if giveaway.status not in (
                GiveawayStatus.WINNER_PENDING_CLAIM,
                GiveawayStatus.COMPLETED,
            ):
                return False, "A giveaway must have a completed draw before it can be rerolled."
            previous_winners = {
                int(member_id)
                for member_id in (
                    await session.execute(
                        select(GiveawayDraw.winner_order).where(
                            GiveawayDraw.giveaway_id == giveaway_id
                        )
                    )
                ).scalars().all()
                for member_id in (member_id or [])
            }
            entries = list(
                (
                    await session.execute(
                        select(GiveawayEntry).where(
                            GiveawayEntry.giveaway_id == giveaway_id,
                            GiveawayEntry.eligibility_status == "eligible",
                        )
                    )
                ).scalars().all()
            )
            members = {member.id: member for member in guild.members}
            eligible = []
            for entry in entries:
                member = members.get(entry.member_id)
                if member and entry.member_id not in previous_winners:
                    ok, failure = await self.check_eligibility(giveaway, member)
                    entry.last_revalidated_at = datetime.utcnow()
                    entry.eligibility_status = "eligible" if ok else "ineligible"
                    entry.eligibility_failure_reason = failure or None
                    if ok:
                        eligible.append(entry)
            if not eligible:
                return False, "No eligible replacement entries remain."
            seed = secrets.token_hex(32)
            ranked = sorted(
                sorted(eligible, key=lambda item: item.id),
                key=lambda item: hashlib.sha256(
                    f"{seed}:{item.id}".encode()
                ).hexdigest(),
            )
            winners = ranked[: min(giveaway.winner_count, len(ranked))]
            draw_count = len(
                (
                    await session.execute(
                        select(GiveawayDraw).where(
                            GiveawayDraw.giveaway_id == giveaway_id
                        )
                    )
                ).scalars().all()
            )
            draw = GiveawayDraw(
                giveaway_id=giveaway_id,
                draw_number=draw_count + 1,
                eligible_entry_count=len(eligible),
                winner_order=[item.member_id for item in winners],
                seed_hash=hashlib.sha256(seed.encode()).hexdigest(),
                reveal_seed=seed,
                reason=reason[:255] or "administrator_reroll",
                created_by=actor_id,
            )
            session.add(draw)
            await session.flush()
            deadline = datetime.utcnow() + timedelta(seconds=giveaway.claim_window_seconds)
            for position, entry in enumerate(winners, 1):
                session.add(
                    GiveawayWinner(
                        draw_id=draw.id,
                        giveaway_id=giveaway_id,
                        member_id=entry.member_id,
                        position=position,
                        claim_deadline=deadline,
                    )
                )
            giveaway.status = GiveawayStatus.WINNER_PENDING_CLAIM
            await session.commit()
        await self._announce_winners(guild, giveaway_id, winners, deadline)
        await AuditService.log_action(
            guild.id, actor_id, "GIVEAWAY_REROLLED",
            {"giveaway_id": giveaway_id, "reason": reason},
        )
        return True, "Giveaway rerolled."

    async def claim(self, guild: discord.Guild, member: discord.Member, giveaway_id: int) -> tuple[bool, str]:
        async with get_db_session() as session:
            winner = (
                await session.execute(
                    select(GiveawayWinner).where(
                        GiveawayWinner.giveaway_id == giveaway_id,
                        GiveawayWinner.member_id == member.id,
                    ).order_by(GiveawayWinner.id.desc())
                )
            ).scalars().first()
            if not winner:
                return False, "You are not a selected winner."
            if winner.claim_status != ClaimStatus.PENDING:
                return False, "This winner record is no longer claimable."
            if datetime.utcnow() >= winner.claim_deadline:
                winner.claim_status = ClaimStatus.EXPIRED
                winner.expired_at = datetime.utcnow()
                await session.commit()
                return False, "The claim deadline has passed."
            winner.claim_status = ClaimStatus.CLAIMED
            winner.claimed_at = datetime.utcnow()
            await session.commit()
        await AuditService.log_action(
            guild.id, member.id, "GIVEAWAY_WINNER_CLAIMED",
            {"giveaway_id": giveaway_id, "member_id": member.id},
        )
        return True, "Claim recorded. The organizer has been notified."

    async def expire_claims(self) -> int:
        now = datetime.utcnow()
        async with get_db_session() as session:
            winners = list(
                (
                    await session.execute(
                        select(GiveawayWinner).where(
                            GiveawayWinner.claim_status == ClaimStatus.PENDING,
                            GiveawayWinner.claim_deadline <= now,
                        )
                    )
                ).scalars().all()
            )
            affected = set()
            for winner in winners:
                winner.claim_status = ClaimStatus.EXPIRED
                winner.expired_at = now
                affected.add(winner.giveaway_id)
            for giveaway_id in affected:
                pending = (
                    await session.execute(
                        select(GiveawayWinner).where(
                            GiveawayWinner.giveaway_id == giveaway_id,
                            GiveawayWinner.claim_status == ClaimStatus.PENDING,
                        )
                    )
                ).scalars().first()
                if not pending:
                    giveaway = await session.get(Giveaway, giveaway_id)
                    if giveaway and giveaway.status == GiveawayStatus.WINNER_PENDING_CLAIM:
                        giveaway.status = GiveawayStatus.COMPLETED
            await session.commit()
        return len(winners)

    async def restore_views(self) -> int:
        from bot.views.giveaways import GiveawayMemberView

        restored = 0
        async with get_db_session() as session:
            giveaways = list(
                (
                    await session.execute(
                        select(Giveaway).where(
                            Giveaway.status.in_(
                                [
                                    GiveawayStatus.SCHEDULED,
                                    GiveawayStatus.LIVE,
                                    GiveawayStatus.WINNER_PENDING_CLAIM,
                                ]
                            ),
                            Giveaway.message_id.is_not(None),
                        )
                    )
                ).scalars().all()
            )
        for giveaway in giveaways:
            guild = self.bot.get_guild(giveaway.guild_id)
            if not guild:
                continue
            channel = guild.get_channel(giveaway.channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                await channel.fetch_message(giveaway.message_id)
                self.bot.add_view(GiveawayMemberView(self.bot, giveaway.id))
                restored += 1
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning(
                    "giveaway.restore_failed",
                    giveaway_id=giveaway.id,
                    guild_id=guild.id,
                )
        return restored