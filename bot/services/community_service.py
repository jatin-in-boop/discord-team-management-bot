from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Optional

import discord
from sqlalchemy import select

from app_logging.logger import get_logger
from bot.services.audit_service import AuditService
from database.session import get_db_session
from models.models import (
    AuditLog,
    CommunitySettings,
    Guild as DbGuild,
    ManagedRoleOwnerType,
    ManagedRoleRegistry,
    ReactionRoleOption,
    Role as DbRole,
    RoleSource,
    RoleType,
)

logger = get_logger(__name__)

WELCOME_DEFAULT = {
    "style": "embed",
    "title": "A NEW SIGNAL HAS ARRIVED",
    "description": (
        "{member_name} has entered {server}.\n\n"
        "Every great community is shaped by the people who show up. "
        "Your signal is now part of the constellation."
    ),
    "footer": "Welcome to the constellation",
    "thumbnail": True,
    "mention": True,
}

GOODBYE_DEFAULT = {
    "style": "embed",
    "title": "A SIGNAL HAS LEFT THE CONSTELLATION",
    "description": (
        "{member_name} has departed from {server}.\n\n"
        "The room changes when a signal moves on. "
        "Their place in the story remains."
    ),
    "footer": "The constellation remembers",
    "thumbnail": False,
    "mention": True,
}

VARIABLES = {
    "welcome": {
        "member", "member_name", "username", "server", "member_count",
        "created_at", "joined_at",
    },
    "goodbye": {
        "member_name", "username", "server", "member_count", "joined_at", "left_at",
    },
}


def _format_dt(value: Optional[datetime]) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else "Unknown"


def _values(guild: discord.Guild, member: Any, kind: str) -> dict[str, str]:
    joined_at = getattr(member, "joined_at", None)
    created_at = getattr(member, "created_at", None)
    left_at = getattr(member, "left_at", None)
    return {
        "member": getattr(member, "mention", ""),
        "member_name": getattr(member, "display_name", None) or getattr(member, "name", "Member"),
        "username": str(getattr(member, "name", "Member")),
        "server": guild.name,
        "member_count": str(guild.member_count or len(guild.members)),
        "created_at": _format_dt(created_at),
        "joined_at": _format_dt(joined_at),
        "left_at": _format_dt(left_at),
    }


def departure_snapshot(member: discord.Member) -> Any:
    return SimpleNamespace(
        id=member.id,
        name=member.name,
        display_name=member.display_name,
        mention=f"<@{member.id}>",
        joined_at=member.joined_at,
        created_at=member.created_at,
        left_at=datetime.utcnow(),
        display_avatar=member.display_avatar,
    )


def validate_template(template: str, kind: str) -> list[str]:
    unknown = sorted(set(re.findall(r"{([^{}]+)}", template)) - VARIABLES[kind])
    unsafe = [token for token in ("@everyone", "@here") if token in template]
    errors = [f"Unknown variable: {{{name}}}" for name in unknown]
    errors.extend(f"Mentions are not allowed: {token}" for token in unsafe)
    return errors


def render_template(template: str, guild: discord.Guild, member: Any, kind: str) -> str:
    values = _values(guild, member, kind)
    return re.sub(
        r"{([^{}]+)}",
        lambda match: values.get(match.group(1), match.group(0)),
        template,
    )


def build_config_embed(
    config: dict[str, Any],
    guild: discord.Guild,
    member: Any,
    kind: str,
    *,
    test: bool = False,
) -> discord.Embed:
    defaults = WELCOME_DEFAULT if kind == "welcome" else GOODBYE_DEFAULT
    merged = {**defaults, **config}
    title = render_template(merged.get("title", ""), guild, member, kind)
    description = render_template(merged.get("description", ""), guild, member, kind)
    is_welcome = kind == "welcome"
    accent = 0xD6A84F if is_welcome else 0x7F8EA8
    embed = discord.Embed(
        title=title or None,
        description=description,
        color=accent,
        timestamp=datetime.utcnow(),
    )
    author = {
        "name": f"{guild.name}  ·  {'NEW ARRIVAL' if is_welcome else 'FAREWELL'}"
    }
    if guild.icon:
        author["icon_url"] = guild.icon.url
    embed.set_author(**author)
    footer = render_template(merged.get("footer", ""), guild, member, kind)
    if footer:
        embed.set_footer(text=footer)
    if test:
        embed.set_footer(text=f"TEST MESSAGE  •  {footer}" if footer else "TEST MESSAGE")
    if merged.get("thumbnail") and getattr(member, "display_avatar", None):
        embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="MEMBER", value=getattr(member, "mention", "New member"), inline=True)
    embed.add_field(
        name="COMMUNITY SIZE",
        value=f"{guild.member_count or len(guild.members):,} members",
        inline=True,
    )
    if is_welcome:
        embed.add_field(
            name="FIRST SIGNAL",
            value="Choose your roles, find your people, and make the room yours.",
            inline=False,
        )
    else:
        embed.add_field(
            name="FINAL SIGNAL",
            value="Thank you for being part of the story.",
            inline=False,
        )
    return embed


class CommunityService:
    @staticmethod
    async def get_or_create_settings(guild: discord.Guild) -> CommunitySettings:
        async with get_db_session() as session:
            result = await session.execute(
                select(CommunitySettings).where(CommunitySettings.guild_id == guild.id)
            )
            settings = result.scalar_one_or_none()
            if settings:
                return settings
            settings = CommunitySettings(
                guild_id=guild.id,
                welcome_message_config=dict(WELCOME_DEFAULT),
                goodbye_message_config=dict(GOODBYE_DEFAULT),
            )
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
            return settings

    @staticmethod
    async def save_message_config(
        guild: discord.Guild,
        executor: discord.Member,
        kind: str,
        channel_id: int,
        config: dict[str, Any],
    ) -> tuple[bool, str]:
        errors = validate_template(config.get("title", ""), kind)
        errors.extend(validate_template(config.get("description", ""), kind))
        errors.extend(validate_template(config.get("footer", ""), kind))
        if errors:
            return False, "\n".join(errors)
        async with get_db_session() as session:
            result = await session.execute(
                select(CommunitySettings).where(CommunitySettings.guild_id == guild.id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = CommunitySettings(
                    guild_id=guild.id,
                    welcome_message_config=dict(WELCOME_DEFAULT),
                    goodbye_message_config=dict(GOODBYE_DEFAULT),
                )
                session.add(settings)
            if kind == "welcome":
                settings.welcome_channel_id = channel_id
                settings.welcome_message_config = config
                settings.welcome_status = None
            else:
                settings.goodbye_channel_id = channel_id
                settings.goodbye_message_config = config
                settings.goodbye_status = None
            settings.updated_by = executor.id
            await session.commit()
        await AuditService.log_action(
            guild.id, executor.id, f"{kind.upper()}_CONFIG_UPDATED",
            {"channel_id": channel_id, "style": config.get("style", "plain")},
        )
        return True, "Saved successfully."

    @staticmethod
    async def set_enabled(
        guild: discord.Guild, executor: discord.Member, kind: str, enabled: bool
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            result = await session.execute(
                select(CommunitySettings).where(CommunitySettings.guild_id == guild.id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = CommunitySettings(
                    guild_id=guild.id,
                    welcome_message_config=dict(WELCOME_DEFAULT),
                    goodbye_message_config=dict(GOODBYE_DEFAULT),
                )
                session.add(settings)
            channel_id = settings.welcome_channel_id if kind == "welcome" else settings.goodbye_channel_id
            if enabled and not channel_id:
                return False, "Choose a destination channel before enabling this feature."
            if kind == "welcome":
                settings.welcome_enabled = enabled
            else:
                settings.goodbye_enabled = enabled
            settings.updated_by = executor.id
            await session.commit()
        await AuditService.log_action(
            guild.id, executor.id, f"{kind.upper()}_CONFIG_{'ENABLED' if enabled else 'DISABLED'}"
        )
        return True, "Enabled." if enabled else "Disabled."

    @staticmethod
    async def reset(guild: discord.Guild, executor: discord.Member, kind: str) -> None:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings:
                return
            if kind == "welcome":
                settings.welcome_enabled = False
                settings.welcome_channel_id = None
                settings.welcome_message_config = dict(WELCOME_DEFAULT)
            else:
                settings.goodbye_enabled = False
                settings.goodbye_channel_id = None
                settings.goodbye_message_config = dict(GOODBYE_DEFAULT)
            settings.updated_by = executor.id
            await session.commit()
        await AuditService.log_action(guild.id, executor.id, f"{kind.upper()}_CONFIG_RESET")

    @staticmethod
    async def mark_status(guild_id: int, kind: str, status: str) -> None:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == guild_id)
                )
            ).scalar_one_or_none()
            if settings:
                if kind == "welcome":
                    settings.welcome_status = status
                else:
                    settings.goodbye_status = status
                await session.commit()

    @staticmethod
    async def send_configured_message(
        guild: discord.Guild,
        member: Any,
        kind: str,
        *,
        test: bool = False,
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            settings = (
                await session.execute(
                    select(CommunitySettings).where(CommunitySettings.guild_id == guild.id)
                )
            ).scalar_one_or_none()
            if not settings:
                return False, "Community settings are not configured."
            enabled = settings.welcome_enabled if kind == "welcome" else settings.goodbye_enabled
            channel_id = settings.welcome_channel_id if kind == "welcome" else settings.goodbye_channel_id
            config = (
                settings.welcome_message_config
                if kind == "welcome"
                else settings.goodbye_message_config
            ) or (dict(WELCOME_DEFAULT) if kind == "welcome" else dict(GOODBYE_DEFAULT))
        if not enabled and not test:
            return False, f"{kind.title()} messages are disabled."
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await CommunityService.mark_status(guild.id, kind, "Destination channel is missing.")
            return False, "The configured destination channel is missing or unavailable."
        try:
            content = render_template(config.get("description", ""), guild, member, kind)
            if config.get("style") == "embed":
                mention = getattr(member, "mention", "")
                await channel.send(
                    content=mention if config.get("mention", True) else None,
                    embed=build_config_embed(config, guild, member, kind, test=test),
                    allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False
                    ),
                )
            else:
                prefix = "[TEST] " if test else ""
                title = render_template(config.get("title", ""), guild, member, kind)
                mention = getattr(member, "mention", "")
                if title:
                    content = f"**{prefix}{title}**\n{content}"
                elif prefix:
                    content = f"**{prefix.rstrip()}**\n{content}"
                if config.get("mention", True):
                    content = f"{mention}\n{content}" if mention else content
                await channel.send(
                    content=content,
                    allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False
                    ),
                )
            await CommunityService.mark_status(guild.id, kind, None)
            return True, "Message sent."
        except discord.Forbidden:
            await CommunityService.mark_status(guild.id, kind, "The bot lacks permission to send messages.")
            return False, "The bot cannot send messages in the configured channel."
        except discord.HTTPException as exc:
            await CommunityService.mark_status(guild.id, kind, f"Discord error: {exc}")
            logger.error("community.message_send_failed", guild_id=guild.id, kind=kind, error=str(exc))
            return False, "Discord could not send the configured message."

    @staticmethod
    async def event_already_logged(guild_id: int, action: str, event_key: str) -> bool:
        async with get_db_session() as session:
            rows = (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.guild_id == guild_id, AuditLog.action == action)
                    .order_by(AuditLog.timestamp.desc())
                    .limit(100)
                )
            ).scalars()
            return any((row.audit_metadata or {}).get("event_key") == event_key for row in rows)

    @staticmethod
    async def role_is_protected(guild_id: int, role_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(DbRole.role_type).where(
                    DbRole.guild_id == guild_id,
                    DbRole.discord_role_id == role_id,
                )
            )
            role_type = result.scalar_one_or_none()
            return role_type == RoleType.TEAM_LEADER

    @staticmethod
    async def validate_role(guild: discord.Guild, role: discord.Role) -> tuple[bool, str]:
        if role.guild.id != guild.id:
            return False, "That role belongs to another server."
        if role.is_default():
            return False, "The @everyone role cannot be used."
        if role.managed:
            return False, "Roles managed by integrations cannot be used."
        if await CommunityService.role_is_protected(guild.id, role.id):
            return False, "Team Leader roles are protected and cannot be used here."
        me = guild.me
        if not me or not me.guild_permissions.manage_roles:
            return False, "The bot needs Manage Roles permission."
        if role >= me.top_role:
            return False, "Move the role below the bot's highest role in Discord."
        return True, ""

    @staticmethod
    async def register_managed_role(
        guild_id: int,
        role: discord.Role,
        owner_record_id: int,
        owner_type: ManagedRoleOwnerType,
        brand_config: dict[str, Any],
        reason: str,
    ) -> ManagedRoleRegistry:
        async with get_db_session() as session:
            registry = ManagedRoleRegistry(
                guild_id=guild_id,
                discord_role_id=role.id,
                owner_type=owner_type,
                owner_record_id=owner_record_id,
                generated_name=role.name,
                brand_tag=brand_config.get("brand_tag"),
                color=role.color.value,
                symbol=brand_config.get("symbol"),
                creation_reason=reason,
            )
            session.add(registry)
            await session.flush()
            return registry

    @staticmethod
    async def parse_color(value: str) -> discord.Color:
        value = value.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
            raise ValueError("Color must be a six-digit hex value such as #5865F2.")
        return discord.Color(int(value, 16))
