import discord
from app_logging.logger import get_logger
from database.engine import engine
from sqlalchemy import text
from datetime import datetime, timezone

logger = get_logger(__name__)


class HealthService:
    """Basic health check system as required in Phase 1.3."""

    @staticmethod
    async def check_database() -> bool:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("health.database_failed", error=str(e))
            return False

    @staticmethod
    async def check_discord(bot) -> bool:
        return bot.is_ready() and bot.user is not None

    @staticmethod
    async def full_health_check(bot) -> dict:
        return {
            "database": await HealthService.check_database(),
            "discord": await HealthService.check_discord(bot),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
