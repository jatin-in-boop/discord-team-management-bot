from datetime import datetime
from typing import Optional, Any, Dict
from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import AuditLog
from sqlalchemy import select
from bot.services.server_log_service import ServerLogService

logger = get_logger(__name__)


class AuditService:
    """Reusable audit logging service."""

    @staticmethod
    async def log_action(
        guild_id: int,
        executor_id: int,
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        async with get_db_session() as session:
            audit = AuditLog(
                guild_id=guild_id,
                executor_id=executor_id,
                action=action,
                audit_metadata=metadata or {},
                timestamp=datetime.utcnow()
            )
            session.add(audit)
            await session.commit()
            logger.info("audit.logged", guild_id=guild_id, action=action)
        await ServerLogService.queue_audit(guild_id, action, executor_id, metadata)
