import logging
import sys

import structlog

from config.settings import get_settings


def setup_logging() -> structlog.stdlib.BoundLogger:
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("discord-team-bot")


logger: structlog.stdlib.BoundLogger = setup_logging()


def get_logger(name: str = "discord-team-bot") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)