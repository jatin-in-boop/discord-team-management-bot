from __future__ import annotations

import asyncio
from datetime import datetime

from app_logging.logger import get_logger
from models.models import Giveaway, GiveawayStatus
from database.session import get_db_session
from sqlalchemy import select

logger = get_logger(__name__)


class CommunityScheduler:
    def __init__(self, bot, pulse_service, giveaway_service):
        self.bot = bot
        self.pulse_service = pulse_service
        self.giveaway_service = giveaway_service
        self.task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        if not self.task or self.task.done():
            self._stopping = False
            self.task = asyncio.create_task(self.run(), name="community-scheduler")

    async def run(self) -> None:
        while not self._stopping:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("community.scheduler_tick_failed")
            await asyncio.sleep(60)

    async def tick(self) -> None:
        now = datetime.utcnow()
        from bot.services.mech_arena_service import MechArenaService

        # Source refreshes are global, read-only, and serialized internally.
        # A failure is logged by the service and must not stop community jobs.
        await MechArenaService.refresh_sources()
        await self.giveaway_service.expire_claims()
        for guild in self.bot.guilds:
            await self.pulse_service.refresh_leaderboard(guild)
            await self.pulse_service.award_voice_blocks(guild)
            await self.pulse_service.sync_band_roles(guild)
            async with get_db_session() as session:
                due = list(
                    (
                        await session.execute(
                            select(Giveaway).where(
                                Giveaway.guild_id == guild.id,
                                Giveaway.status.in_(
                                    [GiveawayStatus.SCHEDULED, GiveawayStatus.LIVE]
                                ),
                                Giveaway.end_at <= now,
                            )
                        )
                    ).scalars().all()
                )
                scheduled = list(
                    (
                        await session.execute(
                            select(Giveaway).where(
                                Giveaway.guild_id == guild.id,
                                Giveaway.status == GiveawayStatus.SCHEDULED,
                                Giveaway.start_at <= now,
                            )
                        )
                    ).scalars().all()
                )
            for giveaway in scheduled:
                await self.giveaway_service.publish(guild, giveaway.id)
            for giveaway in due:
                await self.giveaway_service.end(guild, giveaway.id)

    async def stop(self) -> None:
        self._stopping = True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)