from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from database.engine import async_session
from app_logging.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("database.session_error", error=str(e))
        raise
    finally:
        await session.close()
