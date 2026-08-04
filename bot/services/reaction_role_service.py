from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from typing import Optional

import discord
from sqlalchemy import select, func

from app_logging.logger import get_logger
from bot.services.audit_service import AuditService
from bot.services.community_service import CommunityService
from database.session import get_db_session
from models.models import (
    ManagedRoleOwnerType,
    ManagedRoleRegistry,
    ReactionRoleGroup,
    ReactionRoleOption,
    ReactionRolePanel,
    RoleSource,
    SelectionMode,
    TogglePolicy,
    Guild as DbGuild,
)

logger = get_logger(__name__)

_member_locks: dict[tuple[int, int, Optional[int]], asyncio.Lock] = defaultdict(asyncio.Lock)


def _role_name(label: str, brand_tag: str = "", symbol: str = "") -> str:
    prefix = f"{symbol.strip()} " if symbol.strip() else ""
    brand = f"{brand_tag.strip()} " if brand_tag.strip() else ""
    name = re.sub(r"\s+", " ", f"{prefix}{brand}{label.strip()}").strip()
    return name[:100] or "Community Role"


class ReactionRoleService:
    def __init__(self, bot):
        self.bot = bot

    async def create_panel(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        *,
        name: str,
        channel_id: int,
        mode: str,
        title: str,
        description: str,
    ) -> ReactionRolePanel:
        from models.models import PresentationMode

        try:
            presentation_mode = PresentationMode(mode)
        except ValueError:
            presentation_mode = PresentationMode.BUTTONS

        async with get_db_session() as session:
            panel = ReactionRolePanel(
                guild_id=guild.id,
                name=name[:100],
                channel_id=channel_id,
                presentation_mode=presentation_mode,
                title=title[:256] or name[:256],
                description=description[:4000] or "Choose your roles below.",
                created_by=executor.id,
                updated_by=executor.id,
                appearance={},
            )
            session.add(panel)
            await session.flush()
            await AuditService.log_action(
                guild.id,
                executor.id,
                "REACTION_PANEL_CREATED",
                {"panel_id": panel.id, "name": panel.name, "channel_id": channel_id},
            )
            return panel

    async def add_existing_role(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        panel_id: int,
        role: discord.Role,
        *,
        label: Optional[str] = None,
        description: str = "",
        emoji: str = "",
        group_id: Optional[int] = None,
    ) -> tuple[bool, str, Optional[int]]:
        valid, error = await CommunityService.validate_role(guild, role)
        if not valid:
            return False, error, None
        async with get_db_session() as session:
            duplicate = (
                await session.execute(
                    select(ReactionRoleOption).where(
                        ReactionRoleOption.panel_id == panel_id,
                        ReactionRoleOption.role_id == role.id,
                    )
                )
            ).scalar_one_or_none()
            if duplicate:
                return False, "That role is already in this panel.", None
            panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if not panel or panel.guild_id != guild.id:
                return False, "Panel not found.", None
            option_count = (
                await session.execute(
                    select(func.count(ReactionRoleOption.id)).where(
                        ReactionRoleOption.panel_id == panel_id
                    )
                )
            ).scalar_one()
            option = ReactionRoleOption(
                panel_id=panel_id,
                group_id=group_id,
                role_id=role.id,
                role_source=RoleSource.EXISTING,
                label=(label or role.name)[:100],
                description=description[:100] or None,
                emoji=emoji[:100] or None,
                sort_order=option_count,
                brand_config={},
            )
            session.add(option)
            panel.updated_by = executor.id
            await session.flush()
            option_id = option.id
        await AuditService.log_action(
            guild.id,
            executor.id,
            "REACTION_ROLE_OPTION_ADDED",
            {"panel_id": panel_id, "option_id": option_id, "role_id": role.id, "source": "existing"},
        )
        return True, "Role added.", option_id

    async def add_custom_role(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        panel_id: int,
        *,
        label: str,
        role_name: str,
        brand_tag: str,
        symbol: str,
        color: discord.Color,
        mentionable: bool,
        hoist: bool,
        description: str = "",
        emoji: str = "",
        group_id: Optional[int] = None,
    ) -> tuple[bool, str, Optional[int]]:
        if "team leader" in role_name.lower() or "team leader" in label.lower():
            return False, "Team Leader roles are protected and cannot be created through this panel.", None
        final_name = _role_name(role_name or label, brand_tag, symbol)
        try:
            role = await guild.create_role(
                name=final_name,
                color=color,
                hoist=hoist,
                mentionable=mentionable,
                reason=f"Reaction role panel {panel_id} created by {executor}",
            )
        except discord.Forbidden:
            return False, "The bot needs Manage Roles permission to create that role.", None
        except discord.HTTPException as exc:
            logger.error("reaction_role.custom_role_create_failed", guild_id=guild.id, error=str(exc))
            return False, "Discord could not create the custom role. Please try again.", None

        valid, error = await CommunityService.validate_role(guild, role)
        if not valid:
            try:
                await role.delete(reason="Reaction role validation failed")
            except discord.HTTPException:
                pass
            return False, error, None

        async with get_db_session() as session:
            panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if not panel or panel.guild_id != guild.id:
                try:
                    await role.delete(reason="Reaction role panel not found")
                except discord.HTTPException:
                    pass
                return False, "Panel not found.", None
            option_count = (
                await session.execute(
                    select(func.count(ReactionRoleOption.id)).where(
                        ReactionRoleOption.panel_id == panel_id
                    )
                )
            ).scalar_one()
            option = ReactionRoleOption(
                panel_id=panel_id,
                group_id=group_id,
                role_id=role.id,
                role_source=RoleSource.BOT_CREATED,
                label=label[:100],
                description=description[:100] or None,
                emoji=emoji[:100] or None,
                sort_order=option_count,
                brand_config={
                    "role_name": role_name[:100],
                    "brand_tag": brand_tag[:50],
                    "symbol": symbol[:20],
                    "color": color.value,
                    "mentionable": mentionable,
                    "hoist": hoist,
                },
            )
            session.add(option)
            await session.flush()
            registry = ManagedRoleRegistry(
                guild_id=guild.id,
                discord_role_id=role.id,
                owner_type=ManagedRoleOwnerType.REACTION_PANEL,
                owner_record_id=option.id,
                generated_name=role.name,
                brand_tag=brand_tag[:50] or None,
                color=color.value,
                symbol=symbol[:20] or None,
                creation_reason=f"Reaction role panel {panel_id}",
            )
            session.add(registry)
            panel.updated_by = executor.id
            await session.flush()
            option_id = option.id
        await AuditService.log_action(
            guild.id,
            executor.id,
            "REACTION_CUSTOM_ROLE_CREATED",
            {"panel_id": panel_id, "option_id": option_id, "role_id": role.id},
        )
        return True, "Custom role created and added.", option_id

    async def get_panel(self, panel_id: int) -> Optional[ReactionRolePanel]:
        async with get_db_session() as session:
            return (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()

    async def list_panels(self, guild_id: int) -> list[ReactionRolePanel]:
        async with get_db_session() as session:
            return list(
                (
                    await session.execute(
                        select(ReactionRolePanel)
                        .where(ReactionRolePanel.guild_id == guild_id)
                        .order_by(ReactionRolePanel.created_at)
                    )
                ).scalars().all()
            )

    async def panel_data(self, panel_id: int) -> tuple[Optional[ReactionRolePanel], list[ReactionRoleOption], dict[int, ReactionRoleGroup]]:
        async with get_db_session() as session:
            panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if not panel:
                return None, [], {}
            options = list(
                (
                    await session.execute(
                        select(ReactionRoleOption)
                        .where(ReactionRoleOption.panel_id == panel_id)
                        .order_by(ReactionRoleOption.sort_order)
                    )
                ).scalars().all()
            )
            groups = {
                group.id: group
                for group in (
                    await session.execute(
                        select(ReactionRoleGroup)
                        .where(ReactionRoleGroup.panel_id == panel_id)
                        .order_by(ReactionRoleGroup.sort_order)
                    )
                ).scalars().all()
            }
            return panel, options, groups

    async def publish(self, guild: discord.Guild, panel_id: int) -> tuple[bool, str, Optional[int]]:
        from bot.views.reaction_roles import ReactionRolePanelView, panel_embed

        panel, options, groups = await self.panel_data(panel_id)
        if not panel or panel.guild_id != guild.id:
            return False, "Panel not found.", None
        channel = guild.get_channel(panel.channel_id)
        if not isinstance(channel, discord.TextChannel):
            await self._mark_repair(panel_id, "Configured panel channel is missing or is not text.")
            return False, "The configured channel is missing or unavailable.", None
        await self.sync_managed_roles(guild, panel_id)
        panel, options, groups = await self.panel_data(panel_id)
        view = ReactionRolePanelView(
            self.bot, panel.id, options, groups, panel.presentation_mode.value
        )
        message: Optional[discord.Message] = None
        if panel.message_id:
            try:
                message = await channel.fetch_message(panel.message_id)
            except discord.NotFound:
                message = None
        try:
            if message:
                await message.edit(
                    embed=panel_embed(panel, options, groups),
                    view=view if panel.presentation_mode.value != "reactions" else None,
                )
            else:
                message = await channel.send(
                    embed=panel_embed(panel, options, groups),
                    view=view if panel.presentation_mode.value != "reactions" else None,
                )
            if panel.presentation_mode.value == "reactions":
                for option in options:
                    if option.enabled and option.emoji:
                        try:
                            await message.add_reaction(option.emoji)
                        except discord.HTTPException:
                            logger.warning(
                                "reaction_role.reaction_add_failed",
                                guild_id=guild.id,
                                panel_id=panel.id,
                                option_id=option.id,
                            )
        except discord.Forbidden:
            await self._mark_repair(panel_id, "The bot lacks permission to send or edit the panel message.")
            return False, "The bot cannot send or edit messages in that channel.", None
        except discord.HTTPException as exc:
            await self._mark_repair(panel_id, f"Discord rejected the panel message: {exc}")
            return False, "Discord could not publish the panel.", None
        async with get_db_session() as session:
            db_panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if db_panel:
                db_panel.message_id = message.id
                db_panel.needs_repair = False
                db_panel.repair_status = None
                await session.commit()
        return True, "Panel published.", message.id

    async def sync_managed_roles(
        self, guild: discord.Guild, panel_id: Optional[int] = None
    ) -> tuple[int, int]:
        """Repair bot-owned reaction roles without ever touching existing roles."""
        async with get_db_session() as session:
            query = (
                select(ReactionRoleOption, ManagedRoleRegistry)
                .join(
                    ManagedRoleRegistry,
                    ManagedRoleRegistry.discord_role_id == ReactionRoleOption.role_id,
                )
                .join(ReactionRolePanel, ReactionRoleOption.panel_id == ReactionRolePanel.id)
                .where(
                    ReactionRolePanel.guild_id == guild.id,
                    ReactionRoleOption.role_source == RoleSource.BOT_CREATED,
                )
            )
            if panel_id is not None:
                query = query.where(ReactionRoleOption.panel_id == panel_id)
            rows = list((await session.execute(query)).all())

        synced = 0
        failed = 0
        for option, registry in rows:
            role = guild.get_role(option.role_id)
            if not role:
                failed += 1
                await self._mark_repair(option.panel_id, f"Managed role {option.role_id} is missing.")
                await self._update_registry(registry.discord_role_id, "missing", "Discord role is missing.")
                continue
            config = option.brand_config or {}
            desired_name = _role_name(
                config.get("role_name") or option.label,
                config.get("brand_tag", ""),
                config.get("symbol", ""),
            )
            try:
                valid, error = await CommunityService.validate_role(guild, role)
                if not valid:
                    raise ValueError(error)
                changes = {}
                if role.name != desired_name:
                    changes["name"] = desired_name
                if config.get("color") is not None and role.color.value != int(config["color"]):
                    changes["color"] = discord.Color(int(config["color"]))
                if config.get("hoist") is not None and role.hoist != bool(config["hoist"]):
                    changes["hoist"] = bool(config["hoist"])
                if config.get("mentionable") is not None and role.mentionable != bool(config["mentionable"]):
                    changes["mentionable"] = bool(config["mentionable"])
                if changes:
                    await role.edit(reason=f"Synchronize reaction role panel {option.panel_id}", **changes)
                await self._update_registry(
                    registry.discord_role_id,
                    "synced",
                    None,
                    generated_name=desired_name,
                    color=role.color.value,
                )
                synced += 1
            except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
                failed += 1
                await self._mark_repair(option.panel_id, str(exc))
                await self._update_registry(registry.discord_role_id, "error", str(exc))
        return synced, failed

    async def update_custom_role(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        option_id: int,
        *,
        role_name: str,
        brand_tag: str,
        symbol: str,
        color: discord.Color,
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            option = (
                await session.execute(
                    select(ReactionRoleOption).where(ReactionRoleOption.id == option_id)
                )
            ).scalar_one_or_none()
            if not option or option.role_source != RoleSource.BOT_CREATED:
                return False, "Only bot-owned custom roles can be branded here."
            role = guild.get_role(option.role_id)
            if not role:
                await self._mark_repair(option.panel_id, f"Managed role {option.role_id} is missing.")
                return False, "The bot-owned role no longer exists."
            valid, error = await CommunityService.validate_role(guild, role)
            if not valid:
                return False, error
            desired_name = _role_name(role_name or option.label, brand_tag, symbol)
            try:
                await role.edit(
                    name=desired_name,
                    color=color,
                    reason=f"Update custom reaction role {option_id}",
                )
            except discord.Forbidden:
                return False, "The bot cannot manage this role. Check its hierarchy."
            except discord.HTTPException:
                return False, "Discord could not update the custom role."
            config = dict(option.brand_config or {})
            config.update(
                {
                    "role_name": role_name[:100],
                    "brand_tag": brand_tag[:50],
                    "symbol": symbol[:20],
                    "color": color.value,
                }
            )
            option.brand_config = config
            registry = (
                await session.execute(
                    select(ManagedRoleRegistry).where(
                        ManagedRoleRegistry.discord_role_id == option.role_id
                    )
                )
            ).scalar_one_or_none()
            if registry:
                registry.generated_name = desired_name
                registry.brand_tag = brand_tag[:50] or None
                registry.symbol = symbol[:20] or None
                registry.color = color.value
                registry.last_sync_status = "synced"
                registry.last_sync_error = None
            await session.commit()
            panel_id = option.panel_id
        await AuditService.log_action(
            guild.id,
            executor.id,
            "REACTION_CUSTOM_ROLE_BRANDED",
            {"option_id": option_id, "panel_id": panel_id, "role_id": role.id},
        )
        return True, "Custom role branding updated."

    async def validate_panel_resources(self, guild: discord.Guild) -> tuple[int, int]:
        """Validate configured channels, messages, and roles without replacing them."""
        checked = 0
        repairs = 0
        for panel in await self.list_panels(guild.id):
            checked += 1
            channel = guild.get_channel(panel.channel_id)
            if not isinstance(channel, discord.TextChannel):
                repairs += 1
                await self._mark_repair(panel.id, "Configured panel channel is missing or unavailable.")
                continue
            if panel.message_id:
                try:
                    await channel.fetch_message(panel.message_id)
                except discord.NotFound:
                    repairs += 1
                    await self._mark_repair(panel.id, "Published panel message is missing.")
            _, options, _ = await self.panel_data(panel.id)
            for option in options:
                role = guild.get_role(option.role_id)
                if not role:
                    repairs += 1
                    await self._mark_repair(panel.id, f"Configured role {option.role_id} is missing.")
                    continue
                valid, error = await CommunityService.validate_role(guild, role)
                if not valid:
                    repairs += 1
                    await self._mark_repair(panel.id, error)
        return checked, repairs

    async def _update_registry(
        self,
        role_id: int,
        status: str,
        error: Optional[str],
        *,
        generated_name: Optional[str] = None,
        color: Optional[int] = None,
    ) -> None:
        async with get_db_session() as session:
            registry = (
                await session.execute(
                    select(ManagedRoleRegistry).where(
                        ManagedRoleRegistry.discord_role_id == role_id
                    )
                )
            ).scalar_one_or_none()
            if registry:
                registry.last_sync_status = status
                registry.last_sync_error = error[:500] if error else None
                if generated_name is not None:
                    registry.generated_name = generated_name
                if color is not None:
                    registry.color = color
                await session.commit()

    async def delete_option(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        option_id: int,
        *,
        delete_custom_role: bool = False,
    ) -> tuple[bool, str]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ReactionRoleOption).where(ReactionRoleOption.id == option_id)
            )
            option = result.scalar_one_or_none()
            if not option:
                return False, "Role option not found."
            panel_id = option.panel_id
            role = guild.get_role(option.role_id)
            if delete_custom_role and option.role_source == RoleSource.BOT_CREATED and role:
                valid, error = await CommunityService.validate_role(guild, role)
                if not valid:
                    return False, error
                try:
                    await role.delete(reason=f"Delete custom reaction role option {option_id}")
                except discord.HTTPException:
                    return False, "Discord could not delete the bot-owned role."
            registry = (
                await session.execute(
                    select(ManagedRoleRegistry).where(
                        ManagedRoleRegistry.discord_role_id == option.role_id,
                        ManagedRoleRegistry.owner_type == ManagedRoleOwnerType.REACTION_PANEL,
                    )
                )
            ).scalar_one_or_none()
            if registry:
                await session.delete(registry)
            await session.delete(option)
            await session.commit()
        await AuditService.log_action(
            guild.id,
            executor.id,
            "REACTION_ROLE_OPTION_DELETED",
            {"option_id": option_id, "panel_id": panel_id, "deleted_role": delete_custom_role},
        )
        return True, "Role option deleted."

    async def delete_panel(
        self,
        guild: discord.Guild,
        executor: discord.Member,
        panel_id: int,
        *,
        delete_custom_roles: bool = False,
    ) -> tuple[bool, str]:
        panel, options, _ = await self.panel_data(panel_id)
        if not panel or panel.guild_id != guild.id:
            return False, "Panel not found."
        if panel.message_id:
            channel = guild.get_channel(panel.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(panel.message_id)
                    await message.delete(reason=f"Delete reaction role panel {panel_id}")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    return False, "Discord could not delete the panel message."
        for option in options:
            if delete_custom_roles and option.role_source == RoleSource.BOT_CREATED:
                role = guild.get_role(option.role_id)
                if role:
                    valid, error = await CommunityService.validate_role(guild, role)
                    if not valid:
                        return False, error
                    try:
                        await role.delete(reason=f"Delete reaction role panel {panel_id}")
                    except discord.HTTPException:
                        return False, "Discord could not delete one of the bot-owned roles."
        async with get_db_session() as session:
            registry_rows = list(
                (
                    await session.execute(
                        select(ManagedRoleRegistry).where(
                            ManagedRoleRegistry.owner_type == ManagedRoleOwnerType.REACTION_PANEL,
                            ManagedRoleRegistry.owner_record_id.in_([item.id for item in options]),
                        )
                    )
                ).scalars().all()
            )
            for registry in registry_rows:
                await session.delete(registry)
            db_panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if db_panel:
                await session.delete(db_panel)
            await session.commit()
        await AuditService.log_action(
            guild.id,
            executor.id,
            "REACTION_PANEL_DELETED",
            {"panel_id": panel_id, "deleted_custom_roles": delete_custom_roles},
        )
        return True, "Panel deleted. Existing member roles were preserved."

    async def apply_option(
        self,
        guild: discord.Guild,
        member: discord.Member,
        panel_id: int,
        option_id: int,
        *,
        interaction: Optional[discord.Interaction] = None,
        force_add: Optional[bool] = None,
    ) -> tuple[bool, str]:
        panel, options, groups = await self.panel_data(panel_id)
        option = next((item for item in options if item.id == option_id), None)
        if not panel or not panel.enabled or not option or not option.enabled:
            return False, "This role option is unavailable."
        role = guild.get_role(option.role_id)
        if not role:
            await self._mark_repair(panel_id, f"Role {option.role_id} is missing.")
            return False, "This role option is temporarily unavailable."
        valid, error = await CommunityService.validate_role(guild, role)
        if not valid:
            await self._mark_repair(panel_id, error)
            return False, error
        group = groups.get(option.group_id) if option.group_id else None
        lock = _member_locks[(guild.id, member.id, group.id if group else None)]
        async with lock:
            current = role in member.roles
            if force_add is False:
                if not current:
                    return True, f"{role.name} was already removed."
                await member.remove_roles(role, reason=f"Reaction role panel {panel_id}")
                await self._audit_member_change(guild, member, panel_id, option_id, "removed")
                return True, f"Removed {role.name}."
            if group and group.selection_mode == SelectionMode.SINGLE:
                if current and force_add is not True:
                    if group.toggle_policy == TogglePolicy.STRICT:
                        return False, "That is already your selected role in this group."
                    if option.removable:
                        await member.remove_roles(role, reason=f"Reaction role panel {panel_id}")
                        await self._audit_member_change(guild, member, panel_id, option_id, "removed")
                        return True, f"Removed {role.name}."
                else:
                    other_options = [
                        item for item in options
                        if item.group_id == group.id and item.id != option.id and item.enabled
                    ]
                    other_roles = [
                        guild.get_role(item.role_id)
                        for item in other_options
                        if guild.get_role(item.role_id) in member.roles
                    ]
                    if other_roles:
                        await member.remove_roles(
                            *other_roles, reason=f"Single-choice reaction role panel {panel_id}"
                        )
                    if role not in member.roles:
                        await member.add_roles(role, reason=f"Reaction role panel {panel_id}")
                    await self._audit_member_change(guild, member, panel_id, option_id, "selected")
                    return True, f"Preference updated: {role.name}."
            if current and force_add is not True:
                if not option.removable:
                    return False, "This role cannot be removed."
                await member.remove_roles(role, reason=f"Reaction role panel {panel_id}")
                await self._audit_member_change(guild, member, panel_id, option_id, "removed")
                return True, f"Removed {role.name}."
            if role not in member.roles:
                await member.add_roles(role, reason=f"Reaction role panel {panel_id}")
            await self._audit_member_change(guild, member, panel_id, option_id, "added")
            return True, f"Added {role.name}."

    async def _audit_member_change(
        self, guild: discord.Guild, member: discord.Member, panel_id: int, option_id: int, action: str
    ) -> None:
        await AuditService.log_action(
            guild.id,
            member.id,
            f"REACTION_ROLE_{action.upper()}",
            {"panel_id": panel_id, "option_id": option_id},
        )

    async def _mark_repair(self, panel_id: int, status: str) -> None:
        async with get_db_session() as session:
            panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == panel_id)
                )
            ).scalar_one_or_none()
            if panel:
                panel.needs_repair = True
                panel.repair_status = status[:500]
                await session.commit()

    async def restore_views(self) -> int:
        from bot.views.reaction_roles import ReactionRolePanelView

        restored = 0
        for guild in self.bot.guilds:
            await self.validate_panel_resources(guild)
            await self.sync_managed_roles(guild)
            for panel in await self.list_panels(guild.id):
                if not panel.enabled or not panel.message_id:
                    continue
                _, options, groups = await self.panel_data(panel.id)
                if panel.presentation_mode.value != "reactions":
                    self.bot.add_view(
                        ReactionRolePanelView(
                            self.bot, panel.id, options, groups, panel.presentation_mode.value
                        )
                    )
                restored += 1
        return restored

    async def handle_reaction(self, payload: discord.RawReactionActionEvent, adding: bool) -> None:
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        emoji = str(payload.emoji)
        async with get_db_session() as session:
            result = await session.execute(
                select(ReactionRolePanel, ReactionRoleOption)
                .join(ReactionRoleOption, ReactionRoleOption.panel_id == ReactionRolePanel.id)
                .where(
                    ReactionRolePanel.guild_id == payload.guild_id,
                    ReactionRolePanel.message_id == payload.message_id,
                    ReactionRolePanel.enabled.is_(True),
                    ReactionRoleOption.emoji == emoji,
                )
            )
            row = result.first()
        if not row:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        await self.apply_option(
            guild,
            member,
            row[0].id,
            row[1].id,
            force_add=True if adding else False,
        )
