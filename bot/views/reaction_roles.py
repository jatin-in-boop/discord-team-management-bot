from __future__ import annotations

from typing import Optional

import discord
from discord import ui
from sqlalchemy import select

from app_logging.logger import get_logger
from bot.embeds.base import EmbedBuilder
from bot.services.reaction_role_service import (
    DEFAULT_REACTION_EMOJIS,
    ReactionRoleService,
)
from database.session import get_db_session
from models.models import (
    ReactionRoleGroup,
    ReactionRoleOption,
    ReactionRolePanel,
    SelectionMode,
    TogglePolicy,
)

logger = get_logger(__name__)


async def _republish_after_save(
    editor: "PanelEditorView",
    ok: bool,
    message: str,
) -> tuple[bool, str]:
    if not ok:
        return ok, message
    published, publish_message, _ = await editor.service.publish(
        editor.guild,
        editor.panel.id,
    )
    if not published:
        return False, f"{message} Publish failed: {publish_message}"
    return True, f"{message} {publish_message}"


def panel_embed(
    panel: ReactionRolePanel,
    options: list[ReactionRoleOption],
    groups: dict[int, ReactionRoleGroup],
) -> discord.Embed:
    embed = discord.Embed(
        title=panel.title,
        description=panel.description,
        color=(panel.appearance or {}).get("color", 0x5865F2),
    )
    grouped: dict[Optional[int], list[ReactionRoleOption]] = {}
    for option in options:
        if option.enabled:
            grouped.setdefault(option.group_id, []).append(option)
    for group_id, group_options in grouped.items():
        group = groups.get(group_id) if group_id else None
        heading = group.name if group else "Choose your roles"
        if group and group.selection_mode == SelectionMode.SINGLE:
            heading += " — choose one"
        lines = []
        if group and group.description:
            lines.append(group.description)
        for index, option in enumerate(group_options):
            prefix = f"{option.emoji or DEFAULT_REACTION_EMOJIS[index % len(DEFAULT_REACTION_EMOJIS)]} "
            detail = f" — {option.description}" if option.description else ""
            lines.append(f"{prefix}{option.label}{detail}")
        embed.add_field(name=heading, value="\n".join(lines)[:1024], inline=False)
    embed.set_footer(text="Use the controls below. Your response is private.")
    return embed


class ReactionRolePanelView(ui.View):
    def __init__(
        self,
        bot,
        panel_id: int,
        options: list[ReactionRoleOption],
        groups: dict[int, ReactionRoleGroup],
        presentation_mode: str = "buttons",
        select_placeholder: str = "",
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.panel_id = panel_id
        self.options = options
        self.groups = groups
        self.presentation_mode = presentation_mode
        self.select_placeholder = select_placeholder
        self.service = ReactionRoleService(bot)
        self._build_components()

    def _build_components(self):
        grouped: dict[Optional[int], list[ReactionRoleOption]] = {}
        for option in self.options:
            if option.enabled:
                grouped.setdefault(option.group_id, []).append(option)

        button_options = []
        for group_id, items in grouped.items():
            group = self.groups.get(group_id) if group_id else None
            if self.presentation_mode == "select":
                self.add_item(
                    ReactionRoleSelect(
                        self.bot,
                        self.panel_id,
                        items,
                        group,
                        self.service,
                        self.select_placeholder,
                    )
                )
            else:
                button_options.extend(items)

        for index, option in enumerate(button_options[:20]):
            button = ui.Button(
                label=option.label[:80],
                emoji=option.emoji or DEFAULT_REACTION_EMOJIS[index % len(DEFAULT_REACTION_EMOJIS)],
                style=(
                    discord.ButtonStyle.primary
                    if option.group_id
                    else discord.ButtonStyle.secondary
                ),
                custom_id=f"rr:{self.panel_id}:{option.id}",
                row=index // 5,
            )

            async def callback(interaction: discord.Interaction, item=option):
                await self._handle(interaction, item.id)

            button.callback = callback
            self.add_item(button)

    async def _handle(self, interaction: discord.Interaction, option_id: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Server Only", "This control must be used in a server."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        ok, message = await self.service.apply_option(
            interaction.guild,
            interaction.user,
            self.panel_id,
            option_id,
            interaction=interaction,
        )
        await interaction.followup.send(
            embed=EmbedBuilder.success("Role Updated", message)
            if ok
            else EmbedBuilder.error("Role Not Updated", message),
            ephemeral=True,
        )


class ReactionRoleSelect(ui.Select):
    def __init__(self, bot, panel_id, options, group, service, panel_placeholder=""):
        self.bot = bot
        self.panel_id = panel_id
        self.group = group
        self.service = service
        selection_mode = group.selection_mode if group else SelectionMode.MULTIPLE
        max_values = 1 if selection_mode == SelectionMode.SINGLE else min(len(options), 25)
        super().__init__(
            placeholder=(
                panel_placeholder
                or (group.name if group else "Choose your roles")
            )[:150],
            min_values=1,
            max_values=max_values,
            options=[
                discord.SelectOption(
                    label=option.label[:100],
                    value=str(option.id),
                    description=(option.description or "")[:100] or None,
                    emoji=option.emoji or None,
                )
                for option in options[:25]
            ],
            custom_id=f"rrs:{panel_id}:{group.id if group else 0}",
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Server Only", "This control must be used in a server."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        results = []
        for value in self.values:
            ok, message = await self.service.apply_option(
                interaction.guild,
                interaction.user,
                self.panel_id,
                int(value),
                interaction=interaction,
                force_add=True,
            )
            results.append(("✅ " if ok else "⚠️ ") + message)
        await interaction.followup.send(
            embed=EmbedBuilder.info("Role Preferences", "\n".join(results)[:4000]),
            ephemeral=True,
        )


class ReactionRoleAdminView(ui.View):
    def __init__(self, bot, guild: discord.Guild, executor: discord.abc.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.executor = executor

    @classmethod
    async def create(cls, bot, guild: discord.Guild, executor: discord.abc.User):
        view = cls(bot, guild, executor)
        panels = await ReactionRoleService(bot).list_panels(guild.id)
        if panels:
            view.add_item(PanelSelect(bot, guild, executor, panels))
        return view

    @staticmethod
    async def status_embed(guild: discord.Guild) -> discord.Embed:
        panels = await ReactionRoleService(None).list_panels(guild.id)
        lines = []
        for panel in panels[:15]:
            status = "✅" if panel.enabled and not panel.needs_repair else "⚠️"
            lines.append(f"{status} **{panel.name}** · <#{panel.channel_id}> · {panel.presentation_mode.value}")
        return EmbedBuilder.info(
            "🎭 Reaction Roles",
            "\n".join(lines) if lines else "No panels yet.\nChoose **Create Panel** to get started.",
        )

    @ui.button(label="➕ Create Panel", style=discord.ButtonStyle.success)
    async def create_panel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "Create Reaction-Role Panel",
                "Choose a destination channel and presentation mode, then create the panel basics.",
            ),
            view=CreatePanelSetupView(self.bot, self.guild, interaction.user),
            ephemeral=True,
        )

    @ui.button(label="↩ Community Features", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        from bot.views.community_features import CommunityFeaturesView, community_status_embed

        await interaction.response.edit_message(
            embed=await community_status_embed(self.guild),
            view=CommunityFeaturesView(self.bot),
        )


class PanelSelect(ui.Select):
    def __init__(self, bot, guild, executor, panels):
        self.bot = bot
        self.guild = guild
        self.executor = executor
        super().__init__(
            placeholder="Select a panel to manage...",
            options=[
                discord.SelectOption(
                    label=panel.name[:100],
                    value=str(panel.id),
                    description=f"{panel.presentation_mode.value} · {'needs repair' if panel.needs_repair else 'ready'}",
                )
                for panel in panels[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        panel_id = int(self.values[0])
        editor = await PanelEditorView.create(self.bot, self.guild, self.executor, panel_id)
        if not editor:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Panel Not Found", "That panel is no longer available."),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=editor.embed,
            view=editor,
        )


class CreatePanelSetupView(ui.View):
    def __init__(self, bot, guild, executor):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.channel_id: Optional[int] = None
        self.mode = "buttons"
        self.add_item(CreatePanelChannelSelect(self))
        self.add_item(CreatePanelModeSelect(self))

    @ui.button(label="🧩 Enter Panel Basics", style=discord.ButtonStyle.success, row=2)
    async def basics(self, interaction: discord.Interaction, button: ui.Button):
        if not self.channel_id:
            self.channel_id = interaction.channel.id if interaction.channel else None
        await interaction.response.send_modal(CreatePanelModal(self))


class CreatePanelChannelSelect(ui.ChannelSelect):
    def __init__(self, parent):
        self.controller = parent
        super().__init__(
            placeholder="Destination channel (defaults to this channel)",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.controller.channel_id = self.values[0].id
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Channel Selected", self.values[0].mention),
            ephemeral=True,
        )


class CreatePanelModeSelect(ui.Select):
    def __init__(self, parent):
        self.controller = parent
        super().__init__(
            placeholder="Presentation mode",
            options=[
                discord.SelectOption(label="Buttons", value="buttons", description="Compact role buttons"),
                discord.SelectOption(label="Select menu", value="select", description="Grouped role menus"),
                discord.SelectOption(label="Emoji reactions", value="reactions", description="Classic reaction roles"),
            ],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.controller.mode = self.values[0]
        await interaction.response.send_message(
            embed=EmbedBuilder.success("Mode Selected", self.values[0].title()),
            ephemeral=True,
        )


class CreatePanelModal(ui.Modal, title="Create Reaction-Role Panel"):
    def __init__(self, parent: CreatePanelSetupView):
        super().__init__()
        self.controller = parent
        self.name_input = ui.TextInput(label="Panel name", required=True, max_length=100)
        self.title_input = ui.TextInput(label="Panel title", required=True, max_length=256)
        self.description_input = ui.TextInput(
            label="Panel description",
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        for item in (self.name_input, self.title_input, self.description_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.controller.channel_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Channel Required", "Choose a destination channel first."),
                ephemeral=True,
            )
            return
        try:
            panel = await ReactionRoleService(self.controller.bot).create_panel(
                self.controller.guild,
                self.controller.executor,
                name=self.name_input.value.strip(),
                channel_id=self.controller.channel_id,
                mode=self.controller.mode,
                title=self.title_input.value.strip(),
                description=self.description_input.value.strip(),
            )
            editor = await PanelEditorView.create(
                self.controller.bot, self.controller.guild, self.controller.executor, panel.id
            )
            await interaction.response.send_message(
                embed=editor.embed,
                view=editor,
                ephemeral=True,
            )
        except Exception as exc:
            logger.error("reaction_role.panel_create_failed", error=str(exc))
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Panel Not Created", "Unable to save the panel."),
                ephemeral=True,
            )


class PanelEditorView(ui.View):
    def __init__(self, bot, guild, executor, panel, options, groups):
        super().__init__(timeout=600)
        self.bot = bot
        self.guild = guild
        self.executor = executor
        self.panel = panel
        self.options = options
        self.groups = groups
        self.service = ReactionRoleService(bot)
        self.selected_option_id = None
        self.selected_group_id = None
        if groups:
            self.add_item(EditorGroupSelect(self))
        self.add_item(EditorRoleSelect(self))
        if options:
            self.add_item(EditorOptionSelect(self))

    @classmethod
    async def create(cls, bot, guild, executor, panel_id):
        panel, options, groups = await ReactionRoleService(bot).panel_data(panel_id)
        if not panel or panel.guild_id != guild.id:
            return None
        return cls(bot, guild, executor, panel, options, groups)

    @property
    def embed(self):
        group_summary = "\n".join(
            f"• {group.name} · {group.selection_mode.value}"
            for group in self.groups.values()
        ) or "No groups; role options will be independent."
        option_summary = "\n".join(
            f"• {option.emoji or '✦'} {option.label} · <@&{option.role_id}>"
            for option in self.options
        ) or "No role options yet."
        return EmbedBuilder.info(
            f"Edit Panel: {self.panel.name}",
            f"Channel: <#{self.panel.channel_id}>\nMode: **{self.panel.presentation_mode.value}**\n\n"
            f"Menu placeholder: **{(self.panel.appearance or {}).get('select_placeholder', 'Not set')}**\n\n"
            f"**Groups**\n{group_summary}\n\n**Role options**\n{option_summary[:2500]}",
        )

    @ui.button(label="✏️ Edit Panel", style=discord.ButtonStyle.primary, row=3)
    async def edit_panel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(PanelDetailsModal(self))

    @ui.button(label="🔁 Change Mode", style=discord.ButtonStyle.primary, row=3)
    async def change_mode(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "Change Panel Mode",
                "Existing roles, groups, labels, and descriptions will be preserved. "
                "Only settings required by the new mode will be requested.",
            ),
            view=PanelModeChangeView(self),
            ephemeral=True,
        )

    @ui.button(label="➕ Add Group", style=discord.ButtonStyle.secondary, row=3)
    async def add_group(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddGroupModal(self))

    @ui.button(label="🎨 Create Custom Role", style=discord.ButtonStyle.success, row=3)
    async def custom_role(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CustomRoleModal(self))

    @ui.button(label="📍 Edit Channel", style=discord.ButtonStyle.secondary, row=4)
    async def edit_channel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.info(
                "Choose Panel Channel",
                "Select the text channel where this panel should be published.",
            ),
            view=PanelChannelEditView(self),
            ephemeral=True,
        )

    @ui.button(label="✅ Publish", style=discord.ButtonStyle.primary, row=4)
    async def publish(self, interaction: discord.Interaction, button: ui.Button):
        ok, message, _ = await self.service.publish(self.guild, self.panel.id)
        await interaction.response.edit_message(
            embed=EmbedBuilder.success("Panel Published", message)
            if ok
            else EmbedBuilder.error("Panel Not Published", message),
            view=self,
        )

    @ui.button(label="⏸ Pause / Resume", style=discord.ButtonStyle.secondary, row=4)
    async def toggle(self, interaction: discord.Interaction, button: ui.Button):
        async with get_db_session() as session:
            panel = (
                await session.execute(
                    select(ReactionRolePanel).where(ReactionRolePanel.id == self.panel.id)
                )
            ).scalar_one()
            panel.enabled = not panel.enabled
            await session.commit()
            self.panel.enabled = panel.enabled
        await interaction.response.edit_message(
            embed=EmbedBuilder.success("Panel Updated", "Enabled." if self.panel.enabled else "Paused."),
            view=self,
        )

    @ui.button(label="🗑 Delete Panel", style=discord.ButtonStyle.danger, row=4)
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            embed=EmbedBuilder.warning(
                "Delete Reaction-Role Panel?",
                "The panel message will be deleted. Existing member roles are preserved by default.",
            ),
            view=PanelDeleteConfirmView(self),
            ephemeral=True,
        )

    @ui.button(label="↩ Panels", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        view = await ReactionRoleAdminView.create(self.bot, self.guild, self.executor)
        await interaction.response.edit_message(
            embed=await ReactionRoleAdminView.status_embed(self.guild),
            view=view,
        )


class PanelDetailsModal(ui.Modal, title="Edit Reaction-Role Panel"):
    def __init__(self, parent: PanelEditorView):
        super().__init__()
        self.controller = parent
        self.name_input = ui.TextInput(
            label="Panel name",
            default=parent.panel.name,
            required=True,
            max_length=100,
        )
        self.title_input = ui.TextInput(
            label="Panel title",
            default=parent.panel.title,
            required=True,
            max_length=256,
        )
        self.description_input = ui.TextInput(
            label="Panel description",
            default=parent.panel.description,
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        for item in (self.name_input, self.title_input, self.description_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        appearance = self.controller.panel.appearance or {}
        ok, message = await self.controller.service.update_panel(
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
            name=self.name_input.value,
            title=self.title_input.value,
            description=self.description_input.value,
            mode=self.controller.panel.presentation_mode.value,
            select_placeholder=appearance.get("select_placeholder", ""),
        )
        ok, message = await _republish_after_save(self.controller, ok, message)
        updated = await PanelEditorView.create(
            self.controller.bot,
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
        )
        await interaction.response.send_message(
            embed=updated.embed if ok else EmbedBuilder.error("Panel Not Updated", message),
            view=updated if ok else None,
            ephemeral=True,
        )


class PanelChannelEditView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=180)
        self.editor = editor
        self.add_item(PanelChannelSelect(self))


class PanelChannelSelect(ui.ChannelSelect):
    def __init__(self, parent: PanelChannelEditView):
        self.controller = parent
        super().__init__(
            placeholder="Choose a destination channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        editor = self.controller.editor
        channel = self.values[0]
        appearance = editor.panel.appearance or {}
        ok, message = await editor.service.update_panel(
            editor.guild,
            editor.executor,
            editor.panel.id,
            name=editor.panel.name,
            title=editor.panel.title,
            description=editor.panel.description,
            mode=editor.panel.presentation_mode.value,
            select_placeholder=appearance.get("select_placeholder", ""),
            channel_id=channel.id,
        )
        ok, message = await _republish_after_save(self.controller, ok, message)
        updated = await PanelEditorView.create(
            editor.bot, editor.guild, editor.executor, editor.panel.id
        )
        await interaction.response.edit_message(
            embed=updated.embed if ok else EmbedBuilder.error("Channel Not Updated", message),
            view=updated if ok else self.controller,
        )


class PanelModeChangeView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=180)
        self.editor = editor
        self.add_item(PanelModeSelect(self))


class PanelModeSelect(ui.Select):
    def __init__(self, parent: PanelModeChangeView):
        self.controller = parent
        current = parent.editor.panel.presentation_mode.value
        super().__init__(
            placeholder=f"Current mode: {current} · choose a new mode",
            options=[
                discord.SelectOption(
                    label="Buttons",
                    value="buttons",
                    description="Reuse existing roles as clickable buttons.",
                    default=current == "buttons",
                ),
                discord.SelectOption(
                    label="Select menu",
                    value="select",
                    description="Reuse existing roles in menus.",
                    default=current == "select",
                ),
                discord.SelectOption(
                    label="Emoji reactions",
                    value="reactions",
                    description="Reuse existing roles as reactions.",
                    default=current == "reactions",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        mode = self.values[0]
        if mode == "select":
            await interaction.response.send_modal(SelectModeSettingsModal(self.controller.editor))
            return
        await self._save_mode(interaction, mode)

    async def _save_mode(self, interaction: discord.Interaction, mode: str):
        editor = self.controller.editor
        appearance = editor.panel.appearance or {}
        ok, message = await editor.service.update_panel(
            editor.guild,
            editor.executor,
            editor.panel.id,
            name=editor.panel.name,
            title=editor.panel.title,
            description=editor.panel.description,
            mode=mode,
            select_placeholder=appearance.get("select_placeholder", ""),
        )
        ok, message = await _republish_after_save(editor, ok, message)
        updated = await PanelEditorView.create(
            editor.bot, editor.guild, editor.executor, editor.panel.id
        )
        await interaction.response.edit_message(
            embed=updated.embed if ok else EmbedBuilder.error("Mode Not Changed", message),
            view=updated if ok else self.controller,
        )


class SelectModeSettingsModal(ui.Modal, title="Select Menu Settings"):
    def __init__(self, editor: PanelEditorView):
        super().__init__()
        self.editor = editor
        current = (editor.panel.appearance or {}).get("select_placeholder", "")
        self.placeholder_input = ui.TextInput(
            label="Menu placeholder",
            default=current,
            placeholder="Example: Choose your roles...",
            required=False,
            max_length=150,
        )
        self.add_item(self.placeholder_input)

    async def on_submit(self, interaction: discord.Interaction):
        editor = self.editor
        ok, message = await editor.service.update_panel(
            editor.guild,
            editor.executor,
            editor.panel.id,
            name=editor.panel.name,
            title=editor.panel.title,
            description=editor.panel.description,
            mode="select",
            select_placeholder=self.placeholder_input.value,
        )
        ok, message = await _republish_after_save(editor, ok, message)
        updated = await PanelEditorView.create(
            editor.bot, editor.guild, editor.executor, editor.panel.id
        )
        await interaction.response.send_message(
            embed=updated.embed if ok else EmbedBuilder.error("Mode Not Changed", message),
            view=updated if ok else None,
            ephemeral=True,
        )


class EditorGroupSelect(ui.Select):
    def __init__(self, parent):
        self.controller = parent
        super().__init__(
            placeholder="Role group for the next option (optional)",
            options=[
                discord.SelectOption(label="No group", value="none"),
                *[
                    discord.SelectOption(
                        label=group.name[:100],
                        value=str(group.id),
                        description=group.selection_mode.value,
                    )
                    for group in parent.groups.values()
                ],
            ][:25],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.controller.selected_group_id = None if self.values[0] == "none" else int(self.values[0])
        await interaction.response.send_message(
            embed=EmbedBuilder.success(
                "Group Selected",
                f"{self.values[0]}\nChoose an action below to edit this group.",
            ),
            view=GroupActionView(self.controller),
            ephemeral=True,
        )


class GroupActionView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=180)
        self.editor = editor

    @ui.button(label="✏️ Edit Group", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: ui.Button):
        group = self.editor.groups.get(self.editor.selected_group_id)
        if not group:
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Group Not Found", "Refresh the panel editor and try again."),
                view=None,
            )
            return
        await interaction.response.send_modal(GroupEditModal(self.editor, group))

    @ui.button(label="🗑 Delete Group", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        group = self.editor.groups.get(self.editor.selected_group_id)
        if not group:
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Group Not Found", "Refresh the panel editor and try again."),
                view=None,
            )
            return
        await interaction.response.edit_message(
            embed=EmbedBuilder.warning(
                "Delete Role Group?",
                "The group will be removed, but its role options, Discord roles, and member assignments "
                "will be preserved as independent options.",
            ),
            view=GroupDeleteConfirmView(self.editor, group.id),
        )


class GroupEditModal(ui.Modal, title="Edit Role Group"):
    def __init__(self, parent: PanelEditorView, group: ReactionRoleGroup):
        super().__init__()
        self.controller = parent
        self.group = group
        self.name_input = ui.TextInput(
            label="Group name",
            default=group.name,
            required=True,
            max_length=100,
        )
        self.description_input = ui.TextInput(
            label="Group description",
            default=group.description or "",
            required=False,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )
        self.mode_input = ui.TextInput(
            label="Selection: single or multiple",
            default=group.selection_mode.value,
            required=True,
            max_length=10,
        )
        self.toggle_input = ui.TextInput(
            label="Toggle: remove or strict",
            default=group.toggle_policy.value,
            required=True,
            max_length=10,
        )
        self.rules_input = ui.TextInput(
            label="Required / max selections",
            default=f"{'yes' if group.required else 'no'}, {group.max_selections or 'unlimited'}",
            placeholder="Example: yes, 1 or no, unlimited",
            required=True,
            max_length=30,
        )
        for item in (
            self.name_input,
            self.description_input,
            self.mode_input,
            self.toggle_input,
            self.rules_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        mode = self.mode_input.value.strip().lower()
        toggle = self.toggle_input.value.strip().lower()
        parts = [part.strip().lower() for part in self.rules_input.value.split(",", 1)]
        if len(parts) != 2 or parts[0] not in {"yes", "no"}:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid Group Rules",
                    "Use `yes, 1` or `no, unlimited` for required and maximum selections.",
                ),
                ephemeral=True,
            )
            return
        if parts[1] in {"unlimited", "none", "0"}:
            max_selections = None
        elif parts[1].isdigit():
            max_selections = int(parts[1])
        else:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid Group Rules",
                    "Maximum selections must be a number or `unlimited`.",
                ),
                ephemeral=True,
            )
            return
        ok, message = await self.controller.service.update_group(
            self.controller.guild,
            self.controller.executor,
            self.group.id,
            name=self.name_input.value,
            description=self.description_input.value,
            selection_mode=mode,
            toggle_policy=toggle,
            required=parts[0] == "yes",
            max_selections=max_selections,
        )
        ok, message = await _republish_after_save(self.controller, ok, message)
        updated = await PanelEditorView.create(
            self.controller.bot,
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
        )
        await interaction.response.send_message(
            embed=updated.embed if ok else EmbedBuilder.error("Group Not Updated", message),
            view=updated if ok else None,
            ephemeral=True,
        )


class EditorRoleSelect(ui.RoleSelect):
    def __init__(self, parent):
        self.controller = parent
        super().__init__(placeholder="Add an existing Discord role...", row=1)

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        ok, message, _ = await self.controller.service.add_existing_role(
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
            role,
            group_id=getattr(self.controller, "selected_group_id", None),
        )
        updated = await PanelEditorView.create(
            self.controller.bot, self.controller.guild, self.controller.executor, self.controller.panel.id
        )
        if not ok:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Role Not Added", message),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=updated.embed,
            view=updated,
        )


class EditorOptionSelect(ui.Select):
    def __init__(self, parent):
        self.controller = parent
        super().__init__(
            placeholder="Select an option to remove...",
            options=[
                discord.SelectOption(
                    label=option.label[:100],
                    value=str(option.id),
                    description=f"Role ID {option.role_id}",
                    emoji=option.emoji or None,
                )
                for option in parent.options[:25]
            ],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.controller.selected_option_id = int(self.values[0])
        await interaction.response.send_message(
            embed=EmbedBuilder.success(
                "Option Selected",
                "Choose an action below to edit this role option.",
            ),
            view=OptionActionView(self.controller),
            ephemeral=True,
        )


class OptionActionView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=180)
        self.editor = editor

    def _option(self):
        return next(
            (item for item in self.editor.options if item.id == self.editor.selected_option_id),
            None,
        )

    @ui.button(label="✏️ Edit Name / Description", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: ui.Button):
        if not self._option():
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Option Not Found", "Refresh the panel editor and try again."),
                view=None,
            )
            return
        await interaction.response.send_modal(OptionEditModal(self.editor))

    @ui.button(label="😀 Set Emoji", style=discord.ButtonStyle.secondary)
    async def emoji(self, interaction: discord.Interaction, button: ui.Button):
        if not self._option():
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Option Not Found", "Refresh the panel editor and try again."),
                view=None,
            )
            return
        await interaction.response.send_modal(OptionEmojiModal(self.editor))

    @ui.button(label="🖌️ Rebrand Custom Role", style=discord.ButtonStyle.secondary)
    async def rebrand(self, interaction: discord.Interaction, button: ui.Button):
        option = self._option()
        if not option or option.role_source.value != "bot_created":
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Existing Role Protected",
                    "Only bot-owned custom roles can be renamed or recolored here.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(CustomRoleBrandModal(self.editor))

    @ui.button(label="🗑 Remove Option", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: ui.Button):
        if not self._option():
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Option Not Found", "Refresh the panel editor and try again."),
                view=None,
            )
            return
        await interaction.response.edit_message(
            embed=EmbedBuilder.warning(
                "Remove Role Option?",
                "The panel option will be removed. The Discord role and existing member assignments will be preserved.",
            ),
            view=OptionDeleteConfirmView(self.editor),
        )


class OptionEmojiModal(ui.Modal, title="Set Reaction-Role Emoji"):
    def __init__(self, parent: PanelEditorView):
        super().__init__()
        self.controller = parent
        option = next(
            (item for item in parent.options if item.id == parent.selected_option_id),
            None,
        )
        self.emoji_input = ui.TextInput(
            label="Emoji",
            default=option.emoji if option and option.emoji else "🎮",
            placeholder="Example: 🎮 or <:name:123456789>",
            required=True,
            max_length=100,
        )
        self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        ok, message = await self.controller.service.set_option_emoji(
            self.controller.guild,
            self.controller.executor,
            self.controller.selected_option_id,
            self.emoji_input.value,
        )
        ok, message = await _republish_after_save(self.controller, ok, message)
        updated = await PanelEditorView.create(
            self.controller.bot,
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
        )
        await interaction.response.send_message(
            embed=updated.embed if ok else EmbedBuilder.error("Emoji Not Saved", message),
            view=updated if ok else None,
            ephemeral=True,
        )


class OptionEditModal(ui.Modal, title="Edit Role Option"):
    def __init__(self, parent: PanelEditorView):
        super().__init__()
        self.controller = parent
        option = next(
            (item for item in parent.options if item.id == parent.selected_option_id),
            None,
        )
        self.label_input = ui.TextInput(
            label="Member-facing name",
            default=option.label if option else "",
            required=True,
            max_length=100,
        )
        self.description_input = ui.TextInput(
            label="Role description",
            default=option.description if option and option.description else "",
            required=False,
            max_length=100,
        )
        self.add_item(self.label_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        ok, message = await self.controller.service.update_option(
            self.controller.guild,
            self.controller.executor,
            self.controller.selected_option_id,
            label=self.label_input.value,
            description=self.description_input.value,
        )
        ok, message = await _republish_after_save(self.controller, ok, message)
        updated = await PanelEditorView.create(
            self.controller.bot,
            self.controller.guild,
            self.controller.executor,
            self.controller.panel.id,
        )
        await interaction.response.send_message(
            embed=updated.embed if ok else EmbedBuilder.error("Option Not Updated", message),
            view=updated if ok else None,
            ephemeral=True,
        )


class OptionDeleteConfirmView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=120)
        self.editor = editor

    @ui.button(label="Preserve Discord Role", style=discord.ButtonStyle.primary)
    async def preserve(self, interaction: discord.Interaction, button: ui.Button):
        await self._delete(interaction, delete_role=False)

    @ui.button(label="Delete Bot-Owned Role", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: ui.Button):
        await self._delete(interaction, delete_role=True)

    async def _delete(self, interaction: discord.Interaction, *, delete_role: bool):
        ok, message = await self.editor.service.delete_option(
            self.editor.guild,
            self.editor.executor,
            self.editor.selected_option_id,
            delete_custom_role=delete_role,
        )
        updated = await PanelEditorView.create(
            self.editor.bot,
            self.editor.guild,
            self.editor.executor,
            self.editor.panel.id,
        )
        await interaction.response.edit_message(
            embed=(updated.embed if ok else EmbedBuilder.error("Option Not Removed", message)),
            view=updated if ok else None,
        )


class GroupDeleteConfirmView(ui.View):
    def __init__(self, editor: PanelEditorView, group_id: int):
        super().__init__(timeout=120)
        self.editor = editor
        self.group_id = group_id

    @ui.button(label="Delete Group, Preserve Options", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        ok, message = await self.editor.service.delete_group(
            self.editor.guild,
            self.editor.executor,
            self.group_id,
        )
        ok, message = await _republish_after_save(self.editor, ok, message)
        updated = await PanelEditorView.create(
            self.editor.bot,
            self.editor.guild,
            self.editor.executor,
            self.editor.panel.id,
        )
        await interaction.response.edit_message(
            embed=updated.embed if ok else EmbedBuilder.error("Group Not Deleted", message),
            view=updated if ok else self,
        )

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=self.editor.embed,
            view=self.editor,
        )


class PanelDeleteConfirmView(ui.View):
    def __init__(self, editor: PanelEditorView):
        super().__init__(timeout=120)
        self.editor = editor

    @ui.button(label="Delete Panel Only", style=discord.ButtonStyle.primary)
    async def preserve_roles(self, interaction: discord.Interaction, button: ui.Button):
        await self._delete(interaction, delete_roles=False)

    @ui.button(label="Delete Panel + Bot Roles", style=discord.ButtonStyle.danger)
    async def delete_roles(self, interaction: discord.Interaction, button: ui.Button):
        await self._delete(interaction, delete_roles=True)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=self.editor.embed,
            view=self.editor,
        )

    async def _delete(self, interaction: discord.Interaction, *, delete_roles: bool):
        ok, message = await self.editor.service.delete_panel(
            self.editor.guild,
            self.editor.executor,
            self.editor.panel.id,
            delete_custom_roles=delete_roles,
        )
        if not ok:
            await interaction.response.edit_message(
                embed=EmbedBuilder.error("Panel Not Deleted", message),
                view=self,
            )
            return
        await interaction.response.edit_message(
            embed=EmbedBuilder.success("Panel Deleted", message),
            view=None,
        )


class AddGroupModal(ui.Modal, title="Add Role Group"):
    def __init__(self, parent):
        super().__init__()
        self.controller = parent
        self.name_input = ui.TextInput(label="Group name", required=True, max_length=100)
        self.mode_input = ui.TextInput(
            label="Mode: single or multiple",
            default="multiple",
            required=True,
            max_length=10,
        )
        self.toggle_input = ui.TextInput(
            label="Toggle: remove or strict",
            default="remove",
            required=True,
            max_length=10,
        )
        self.add_item(self.name_input)
        self.add_item(self.mode_input)
        self.add_item(self.toggle_input)

    async def on_submit(self, interaction: discord.Interaction):
        mode = self.mode_input.value.strip().lower()
        toggle = self.toggle_input.value.strip().lower()
        if mode not in {"single", "multiple"} or toggle not in {"remove", "strict"}:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Group Rules", "Use single/multiple and remove/strict."),
                ephemeral=True,
            )
            return
        async with get_db_session() as session:
            session.add(
                ReactionRoleGroup(
                    panel_id=self.controller.panel.id,
                    name=self.name_input.value.strip(),
                    selection_mode=SelectionMode(mode),
                    toggle_policy=TogglePolicy(toggle),
                    sort_order=len(self.controller.groups),
                )
            )
            await session.commit()
        updated = await PanelEditorView.create(
            self.controller.bot, self.controller.guild, self.controller.executor, self.controller.panel.id
        )
        await interaction.response.send_message(embed=updated.embed, view=updated, ephemeral=True)


class CustomRoleModal(ui.Modal, title="Create Custom Reaction Role"):
    def __init__(self, parent):
        super().__init__()
        self.controller = parent
        self.label_input = ui.TextInput(label="Member-facing label", required=True, max_length=100)
        self.name_input = ui.TextInput(label="Discord role name", required=True, max_length=100)
        self.brand_input = ui.TextInput(label="Brand tag or prefix", required=False, max_length=50)
        self.symbol_input = ui.TextInput(label="Unicode symbol", default="✦", required=False, max_length=20)
        self.color_input = ui.TextInput(label="Color hex", default="#5865F2", required=True, max_length=7)
        for item in (
            self.label_input,
            self.name_input,
            self.brand_input,
            self.symbol_input,
            self.color_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = await self.controller.service.parse_color(self.color_input.value)
            ok, message, _ = await self.controller.service.add_custom_role(
                self.controller.guild,
                self.controller.executor,
                self.controller.panel.id,
                label=self.label_input.value,
                role_name=self.name_input.value,
                brand_tag=self.brand_input.value,
                symbol=self.symbol_input.value,
                color=color,
                mentionable=False,
                hoist=False,
                group_id=getattr(self.controller, "selected_group_id", None),
            )
            updated = await PanelEditorView.create(
                self.controller.bot, self.controller.guild, self.controller.executor, self.controller.panel.id
            )
            await interaction.response.send_message(
                embed=updated.embed if ok else EmbedBuilder.error("Role Not Created", message),
                view=updated if ok else None,
                ephemeral=True,
            )
        except ValueError as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Role", str(exc)),
                ephemeral=True,
            )


class CustomRoleBrandModal(ui.Modal, title="Rebrand Custom Reaction Role"):
    def __init__(self, parent):
        super().__init__()
        self.controller = parent
        option = next(
            (item for item in parent.options if item.id == parent.selected_option_id),
            None,
        )
        config = option.brand_config if option else {}
        self.name_input = ui.TextInput(
            label="Discord role name",
            default=config.get("role_name", option.label if option else ""),
            required=True,
            max_length=100,
        )
        self.brand_input = ui.TextInput(
            label="Brand tag or prefix",
            default=config.get("brand_tag", ""),
            required=False,
            max_length=50,
        )
        self.symbol_input = ui.TextInput(
            label="Unicode symbol",
            default=config.get("symbol", "✦"),
            required=False,
            max_length=20,
        )
        self.color_input = ui.TextInput(
            label="Color hex",
            default=f"#{int(config.get('color', 0x5865F2)):06X}",
            required=True,
            max_length=7,
        )
        for item in (
            self.name_input,
            self.brand_input,
            self.symbol_input,
            self.color_input,
        ):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = await self.controller.service.parse_color(self.color_input.value)
            ok, message = await self.controller.service.update_custom_role(
                self.controller.guild,
                self.controller.executor,
                self.controller.selected_option_id,
                role_name=self.name_input.value,
                brand_tag=self.brand_input.value,
                symbol=self.symbol_input.value,
                color=color,
            )
            updated = await PanelEditorView.create(
                self.controller.bot,
                self.controller.guild,
                self.controller.executor,
                self.controller.panel.id,
            )
            await interaction.response.send_message(
                embed=(updated.embed if ok else EmbedBuilder.error("Role Not Updated", message)),
                view=updated if ok else None,
                ephemeral=True,
            )
        except ValueError as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid Role", str(exc)),
                ephemeral=True,
            )