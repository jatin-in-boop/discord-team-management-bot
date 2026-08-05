from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

import discord
from sqlalchemy import select

from app_logging.logger import get_logger
from database.session import get_db_session
from models.models import CommunitySettings

logger = get_logger(__name__)

ALL_CATEGORIES = (
    "moderation",
    "members",
    "channels",
    "roles",
    "invites",
    "server",
    "messages",
    "voice",
    "automation",
)
DEFAULT_CATEGORIES = ALL_CATEGORIES[:6]

ACTION_CATEGORIES = {
    "INVITE_CREATED": "invites",
    "INVITE_DELETED": "invites",
    "INVITE_USED": "invites",
    "MEMBER_JOINED": "members",
    "MEMBER_LEFT": "members",
    "MEMBER_UPDATED": "members",
    "MEMBER_ROLE_CHANGED": "members",
    "MEMBER_ROLES_UPDATED": "automation",
    "MEMBER_BANNED": "moderation",
    "MEMBER_UNBANNED": "moderation",
    "MESSAGE_DELETED": "messages",
    "MESSAGE_EDITED": "messages",
    "CHANNEL_CREATED": "channels",
    "CHANNEL_UPDATED": "channels",
    "CHANNEL_DELETED": "channels",
    "ROLE_CREATED": "roles",
    "ROLE_UPDATED": "roles",
    "ROLE_DELETED": "roles",
    "GUILD_UPDATED": "server",
    "VOICE_STATE_UPDATED": "voice",
}


def action_category(action: str) -> str:
    if action in ACTION_CATEGORIES:
        return ACTION_CATEGORIES[action]
    if action.startswith(("REACTION_", "PULSE_", "GIVEAWAY_")):
        return "automation"
    if action.startswith(("TEAM_", "WELCOME_", "GOODBYE_")):
        return "server"
    return "server"


def _display_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value).replace("\n", " ").strip()
    return text[:160]


class ServerLogService:
    """Batches configured audit records into compact Discord summaries."""

    _bot = None
    _pending: dict[int, list[dict[str, Any]]] = defaultdict(list)
    _tasks: dict[int, asyncio.Task] = {}
    _lock = asyncio.Lock()

    @classmethod
    def bind_bot(cls, bot) -> None:
        cls._bot = bot

    @classmethod
    async def queue_audit(
        cls,
        guild_id: int,
        action: str,
        executor_id: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not cls._bot:
            return
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == guild_id)
                )
            ).scalar_one_or_none()
        if not settings or not settings.audit_logging_enabled or not settings.audit_log_channel_id:
            return

        category = action_category(action)
        config = settings.audit_log_config or {}
        enabled_categories = set(config.get("categories") or DEFAULT_CATEGORIES)
        if category == "automation" and not config.get("include_automation", False):
            return
        if category == "messages" and not config.get("include_messages", False):
            return
        if category not in enabled_categories:
            return

        async with cls._lock:
            cls._pending[guild_id].append(
                {
                    "action": action,
                    "category": category,
                    "executor_id": executor_id,
                    "metadata": metadata or {},
                    "timestamp": datetime.utcnow(),
                }
            )
            if guild_id not in cls._tasks or cls._tasks[guild_id].done():
                cls._tasks[guild_id] = asyncio.create_task(cls._flush_later(guild_id))

    @classmethod
    async def _flush_later(cls, guild_id: int) -> None:
        await asyncio.sleep(6)
        await cls.flush(guild_id)

    @classmethod
    async def flush(cls, guild_id: int) -> None:
        async with cls._lock:
            events = cls._pending.pop(guild_id, [])
        if not events or not cls._bot:
            return
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == guild_id)
                )
            ).scalar_one_or_none()
        if not settings or not settings.audit_logging_enabled:
            return
        channel = cls._bot.get_channel(settings.audit_log_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        counts: dict[str, int] = defaultdict(int)
        lines: list[str] = []
        for event in events:
            counts[event["action"]] += 1
            metadata = event["metadata"]
            subject = (
                metadata.get("member_id")
                or metadata.get("user_id")
                or metadata.get("role_id")
                or metadata.get("channel_id")
            )
            subject_text = f" · <@{subject}>" if subject else ""
            details = []
            for key in ("name", "role_name", "channel_name", "inviter_id", "member_id", "reason"):
                if key in metadata and metadata[key] is not None:
                    value = metadata[key]
                    if key.endswith("_id") and key not in ("inviter_id", "member_id"):
                        value = f"<@{value}>"
                    details.append(f"{key.replace('_', ' ')}={_display_value(value)}")
            suffix = f" · {'; '.join(details[:3])}" if details else ""
            actor = (
                f"<@{event['executor_id']}>"
                if event.get("executor_id")
                else "unknown actor"
            )
            lines.append(f"• `{event['action']}` · by {actor}{subject_text}{suffix}")

        summary = ", ".join(
            f"{count}× {action.replace('_', ' ').title()}"
            for action, count in sorted(counts.items())
        )
        embed = discord.Embed(
            title="Server Activity Summary",
            description=f"**{len(events)} event(s) grouped over the last few seconds**\n{summary}",
            color=0x5865F2,
            timestamp=datetime.utcnow(),
        )
        if lines:
            embed.add_field(name="Details", value="\n".join(lines[:20])[:1024], inline=False)
        if len(lines) > 20:
            embed.set_footer(text=f"{len(lines) - 20} additional events were grouped.")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("server_logs.send_failed", guild_id=guild_id, error=str(exc))