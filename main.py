import asyncio
from bot.client import run_bot
from app_logging.logger import get_logger

logger = get_logger(__name__)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("bot.shutdown.keyboard_interrupt")
    except Exception as e:
        logger.critical("bot.crash", error=str(e))
        raise
