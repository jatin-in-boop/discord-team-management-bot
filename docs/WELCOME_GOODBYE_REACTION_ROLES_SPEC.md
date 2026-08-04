# Welcome, Goodbye & Reaction Roles
## Product and Technical Specification

**Status:** Proposed  
**Audience:** Product, design, and implementation teams  
**Primary principle:** Build the most polished, reliable, and easy-to-manage Discord experience possible without turning the bot into an overcomplicated configuration platform.

---

## 1. Purpose

Add three closely related community-management capabilities to the Discord bot:

1. A complete welcome-message system for new members.
2. A complete goodbye-message system for members who leave.
3. A flexible reaction-role system that lets members choose roles themselves, including groups where only one role may be selected.

The system must feel native to Discord, remain simple for administrators, survive bot restarts, and fit the bot’s existing UI-driven architecture.

The existing team-management functionality remains unchanged. In particular:

- The bot may create Team Leader roles.
- The bot must never assign, remove, transfer, or otherwise manage Team Leader roles.
- The new reaction-role feature must not automatically include or control Team Leader roles unless an administrator explicitly configures a separate role panel for a permitted role.
- No slash commands should be introduced. Configuration must use the existing persistent management panel, buttons, modals, and select menus.

---

## 2. Product goals

### 2.1 Main goals

- Give administrators a professional setup experience entirely inside Discord.
- Make common setups fast while allowing detailed customization when needed.
- Make member-facing role selection obvious, attractive, and safe.
- Support both simple single-role panels and large grouped role menus.
- Enforce single-choice groups reliably, even when a member already has a role from that group.
- Make all configuration persistent and recoverable after a restart.
- Provide clear success, validation, and error feedback.
- Keep the feature set focused: no unnecessary social, leveling, ticketing, or moderation systems.

### 2.2 Quality goals

- No duplicate role assignments.
- No accidental removal of roles outside the configured panel.
- No public leakage of administrator configuration actions.
- No stale panels after a message is deleted or a role is removed.
- No silent failures: every failed Discord or database operation must be logged and shown to the administrator in a useful way.
- Configuration should be understandable without reading technical documentation.

### 2.3 Non-goals

The first implementation should not include:

- Automatic welcome DMs.
- Member leveling, XP, or points.
- Moderation automations.
- Scheduled announcements.
- A public web dashboard.
- Slash commands.
- Automatic assignment of Team Leader roles.
- Automatic assignment of a default role on join unless explicitly added as a later, separately approved feature.

---

## 3. Experience architecture

### 3.1 Existing management panel

All administrator configuration is added to the existing persistent management panel. Add one new top-level button:

**`✨ Community Features`**

This opens a private, ephemeral administrator view with three cards/buttons:

- **`👋 Welcome Message`**
- **`🚪 Goodbye Message`**
- **`🎭 Reaction Roles`**

The view should show compact status summaries, for example:

```text
Welcome      ✅ Enabled · #welcome · Custom embed
Goodbye      ⏸ Disabled
Reaction     ✅ 2 panels · 7 role options
```

Only administrators may open or use these controls. Unauthorized users receive an ephemeral response and no configuration details.

### 3.2 Member-facing experience

Member-facing role panels must be persistent Discord messages. They should not require commands.

The primary presentation modes are:

1. **Buttons** — best for a small number of roles.
2. **Select menu** — best for larger groups or compact layouts.
3. **Emoji reaction mode** — supported for familiar “react to receive a role” behavior.

The administrator chooses the presentation mode while creating or editing a panel. The underlying role rules remain the same regardless of presentation mode.

---

## 4. Welcome message system

### 4.1 Core behavior

When a new member joins a configured guild:

1. The bot reads the guild’s welcome configuration.
2. It resolves the configured destination channel.
3. It renders the configured message using safe member and server variables.
4. It sends the message once.
5. It logs the event and any failure.

If the destination channel, message, or required permission is invalid, the bot must not crash. It should log the reason and notify administrators through the configuration status view when they next open it.

### 4.2 Configuration flow

The administrator selects **Welcome Message** and sees:

- Current enabled/disabled status.
- Destination channel.
- Message preview.
- `✏️ Edit`
- `👁 Preview`
- `🔘 Enable / Disable`
- `🧪 Send Test`
- `🗑 Reset`

The edit flow should be a guided modal/wizard:

1. Select destination channel.
2. Choose message style:
   - Plain message.
   - Embed.
3. Enter title, description, and optional footer.
4. Choose whether to show the member avatar thumbnail.
5. Review the rendered preview.
6. Save or cancel.

The simple path should require only a channel and message description. Advanced fields should be optional, not forced.

### 4.3 Welcome message variables

Supported variables:

| Variable | Meaning |
|---|---|
| `{member}` | Mentions the new member |
| `{member_name}` | Member display name |
| `{username}` | Discord username |
| `{server}` | Server name |
| `{member_count}` | Current member count |
| `{created_at}` | Member account creation date |
| `{joined_at}` | Join timestamp |

Unknown variables must remain visible in preview as validation errors and must not be silently removed.

### 4.4 Safety rules

- `{member}` is the only default member mention.
- `@everyone` and `@here` must be escaped or rejected.
- Role mentions should not be accepted through free-form text unless the administrator selects an allowed role through a dedicated role picker.
- Test messages must be clearly marked as test messages.
- The bot must never send a welcome message to an arbitrary channel without an administrator saving that channel in configuration.

### 4.5 Recommended default

On first setup, offer a tasteful default:

```text
Welcome {member} to {server}.
Please take a moment to choose your roles below and review the server guidelines.
```

The default must be editable before enabling.

---

## 5. Goodbye message system

### 5.1 Core behavior

When a member leaves:

1. The bot reads the guild’s goodbye configuration.
2. It renders the configured message.
3. It sends the message once to the configured channel.
4. It logs the event.

The system must work when the member is no longer in the guild. It should use the information available in the Discord event and must not depend on fetching the member after departure.

### 5.2 Configuration flow

The Goodbye Message view mirrors the Welcome Message view:

- Current status.
- Destination channel.
- Preview.
- Edit.
- Enable/disable.
- Send test.
- Reset.

The preview should use a clearly labeled sample member so administrators understand that the actual member may have left the server.

### 5.3 Goodbye variables

Supported variables:

| Variable | Meaning |
|---|---|
| `{member_name}` | Last-known display name |
| `{username}` | Last-known Discord username |
| `{server}` | Server name |
| `{member_count}` | Current member count after departure, where available |
| `{joined_at}` | Join timestamp, where available |
| `{left_at}` | Departure timestamp |

`{member}` should not be supported by default because a departed member cannot reliably be mentioned in every event context.

### 5.4 Privacy and tone

- Do not expose internal moderation information.
- Do not state why a member left unless Discord provides an authoritative reason, which it normally does not.
- Do not make the default message humiliating, accusatory, or overly personal.
- Administrators may choose a custom tone, but the preview should discourage sensitive data.

### 5.5 Recommended default

```text
{member_name} has left {server}.
We wish them all the best.
```

---

## 6. Reaction-role system

### 6.1 Concept

A reaction-role panel is a persistent message containing:

- A title and description.
- Optional image, thumbnail, and footer.
- One or more role options.
- A presentation mode: buttons, select menu, or emoji reactions.
- Optional role groups that control selection rules.

A panel can contain:

- Independent roles, where members may choose any number.
- One or more single-choice groups, where a member may hold only one role within each group.
- A mixture of independent roles and single-choice groups.

Example:

```text
Choose your preferences

Game Platform — choose one:
🎮 PC
🕹 Console
📱 Mobile

Notifications — choose any:
📢 Tournament Updates
🎉 Events
📰 Announcements
```

### 6.2 Role option model

Each role option contains:

- Role ID.
- Role source:
  - Existing administrator-created role.
  - Bot-created custom role owned by this panel.
- Display label.
- Description.
- Emoji or icon.
- Group ID, optional.
- Sort order.
- Enabled/disabled state.
- Whether the member may remove the role by selecting it again.

### 6.3.1 Custom reaction roles

Administrators must be able to create a custom role directly inside the
reaction-role wizard instead of creating it manually in Discord.

The role option flow offers:

- `Use existing role`
- `Create custom role`

For a bot-created custom role, the administrator can configure:

- Role name.
- Brand tag or prefix.
- Role color.
- Unicode symbol or emoji prefix.
- Whether the role is displayed separately in the member list.
- Whether the role is mentionable.
- Optional group assignment.

The wizard shows a live preview:

```text
✦ 𝐏𝐂 𝐏𝐥𝐚𝐲𝐞𝐫
Color: Ocean Blue
Group: Platform · Single choice
Managed by: This reaction-role panel
```

The bot should use a consistent Unicode style for names, but administrators
may choose the visible label and brand prefix. Names must remain readable, fit
Discord limits, and fall back to plain text if a requested character is
unsupported.

Bot-created reaction roles are owned resources. Store their role ID, owner
type, source panel, creation reason, and current branding configuration.

### 6.3.2 Custom role lifecycle

For each bot-created reaction role, administrators can:

- Rename it.
- Change its color.
- Change its symbol or brand tag.
- Move it between groups.
- Disable it temporarily.
- Reuse it in a revised panel.
- Delete it after explicit confirmation.

Deleting a custom role must ask whether to:

1. Delete only the panel option and preserve the Discord role.
2. Delete the panel option and the bot-created Discord role.
3. Delete the role and remove it from members who received it through this panel.

The safe default is to preserve both the Discord role and member assignments.
The bot must never delete an existing administrator-created role through this
workflow.

If the server brand changes, a brand synchronization action updates only
bot-owned reaction roles. Existing administrator-created roles are not renamed
or recolored automatically.

The role’s actual Discord name must not be used as the only display label. Administrators should be able to present a friendly label while retaining the real role.

### 6.3 Group rules

Each panel may define zero or more groups.

Group properties:

- Group name.
- Group description.
- Selection mode:
  - `Multiple choice`
  - `Single choice`
- Required selection:
  - Optional.
  - Required, if supported by the selected UI mode.
- Maximum selections, for future extensibility.
- Sort order.

#### Single-choice behavior

When a member selects a role in a single-choice group:

1. The bot checks the member’s current roles in that group.
2. It removes other roles from the same group.
3. It assigns the selected role.
4. It confirms the change privately.

The bot must not remove:

- Roles outside the group.
- Roles from another reaction-role panel unless they are explicitly part of the same configured group.
- Administrator-managed roles that are not configured in the panel.
- The Team Leader role.

If the member selects the currently held role again, the configured toggle policy applies:

- Default: remove it, leaving the group with no selection.
- Optional strict mode: keep it selected and explain that another choice is required.

The administrator chooses the policy when configuring the group.

### 6.4 Panel creation flow

The administrator selects **Reaction Roles → Create Panel**.

#### Step 1: Panel basics

- Panel name, for administrator reference.
- Destination channel.
- Presentation mode:
  - Buttons.
  - Select menu.
  - Emoji reactions.
- Panel title.
- Panel description.
- Optional color, thumbnail, image, and footer.

#### Step 2: Add role groups

The administrator can create a group:

- `➕ Add Group`
- Group name.
- Group instructions.
- Single-choice or multiple-choice.
- Toggle behavior.

The administrator can also choose **No group** for independent roles.

#### Step 3: Add roles

Offer both an existing-role selector and a `Create custom role` action. For each
role option, configure:

- Label.
- Description.
- Emoji.
- Group.
- Sort order.
- Role source and ownership.
- Optional custom name, symbol, and color when bot-created.

The UI should show a live summary:

```text
Platform — Single choice
  🎮 PC
  🕹 Console
  📱 Mobile

Notifications — Multiple choice
  📢 Tournament Updates
  🎉 Events
```

#### Step 4: Preview and publish

Before publishing, show a full preview that matches the final Discord message as closely as possible.

Actions:

- `← Back`
- `✏️ Edit`
- `🧪 Send Test`
- `✅ Publish`
- `✕ Cancel`

Publishing must create or update the configured message and persist its message ID.

### 6.5 Editing an existing panel

Reaction Roles should show a list of configured panels with:

- Panel name.
- Channel.
- Enabled/disabled status.
- Number of roles.
- Number of single-choice groups.

Actions:

- Edit panel.
- Add/remove role.
- Move role.
- Change group rules.
- Re-render message.
- Pause/resume interactions.
- Send test.
- Delete panel.

Deleting a panel must ask whether to:

1. Delete only the panel message.
2. Delete the panel message and remove roles granted by this panel from members.

The safe default is to delete only the panel message and preserve member roles.

### 6.6 Presentation modes

#### Buttons

Best for up to 5–10 options, depending on Discord component limits and layout.

- Button label is the configured role label.
- Button emoji is optional.
- Button state should communicate success through an ephemeral response.
- Buttons should use consistent styles, not random colors.

Suggested semantic styles:

- Primary: neutral selection.
- Success: active/positive action.
- Secondary: general options.
- Danger: never use for normal role selection.

#### Select menu

Best for larger groups and mixed panels.

- Support one-select mode for a single-choice group.
- Support multi-select mode for multiple-choice groups.
- Show descriptions and emojis where Discord supports them.
- Use one menu per group when groups have different selection rules.

#### Emoji reactions

Best for a classic reaction-role experience.

- Each role option maps to one unique emoji.
- Add configured reactions after publishing.
- On reaction add, assign the role.
- On reaction remove, remove the role if toggle behavior permits.
- Ignore bot reactions.
- Validate that every emoji is unique within the panel.

When a panel contains single-choice groups, the bot should remove the member’s previous group reaction after a new choice is made, then synchronize the roles. If Discord event ordering creates a temporary mismatch, the database and current member roles remain the source of truth.

### 6.7 Role and permission validation

Before saving or publishing:

- The role must exist in the guild.
- A bot-created custom role must be created successfully before the panel can
  be published.
- The bot must be able to manage the role.
- The role must be below the bot’s highest role.
- The role must not be managed by an integration.
- The role must not be `@everyone`.
- The role must not be a Team Leader role created under the existing protected policy.
- A bot-owned role must be clearly identified as bot-owned in the administrator
  configuration view.
- The bot must have the required channel permissions.
- The same role may not appear twice in one panel.
- An emoji may not be reused within one emoji-reaction panel.
- A role may not belong to two groups in the same panel.

If a role becomes unmanageable later because its hierarchy changes, the bot must leave it untouched, mark the option as unavailable, and show the administrator a repair warning.

### 6.8 Role synchronization and repair

On startup and when an administrator opens the reaction-role dashboard, validate
every configured role option:

1. Confirm the role still exists.
2. Confirm the role belongs to the correct guild.
3. Confirm ownership and panel association.
4. Confirm the bot can manage it.
5. Confirm its name and color match the saved brand configuration when the role
   is bot-owned.
6. Offer a repair action for missing, renamed, recolored, or moved resources.

Brand changes should be applied transactionally where possible. If a rename
succeeds but a color update fails, the configuration must show a repair warning
instead of claiming that the role is synchronized.

### 6.9 Member interaction feedback

Every interaction should be private and concise:

Successful examples:

```text
✅ You now have the PC role.
```

```text
✅ Preference updated: Console.
Removed: PC.
```

```text
✅ Added Tournament Updates.
```

Error examples:

```text
⚠️ I can’t manage that role. Please ask an administrator to move it below my bot role.
```

```text
⚠️ This role option is temporarily unavailable.
```

Do not send noisy public messages for ordinary role changes.

---

## 7. Data model

The exact ORM names may follow the existing project conventions, but the system needs these durable concepts.

### 7.1 Guild community settings

One record per guild:

- Guild ID.
- Welcome enabled.
- Welcome channel ID.
- Welcome message configuration.
- Goodbye enabled.
- Goodbye channel ID.
- Goodbye message configuration.
- Updated by.
- Updated timestamp.

Message configuration should be stored as structured JSON rather than one opaque text field so it can support plain messages and embeds without a future breaking migration.

### 7.2 Reaction-role panel

- Guild ID.
- Panel name.
- Channel ID.
- Message ID.
- Presentation mode.
- Enabled state.
- Embed/message configuration.
- Created by.
- Updated by.
- Created and updated timestamps.

Add a unique constraint on `(guild_id, message_id)` where appropriate.

### 7.3 Reaction-role group

- Panel ID.
- Group name.
- Description.
- Selection mode.
- Toggle policy.
- Required flag.
- Sort order.

### 7.4 Reaction-role option

- Panel ID.
- Group ID, nullable.
- Role ID.
- Role source: existing or bot-created.
- Managed ownership: panel ID or administrator-owned.
- Brand configuration JSON.
- Label.
- Description.
- Emoji representation.
- Sort order.
- Enabled state.

Add a unique constraint preventing the same role from appearing more than once in a panel.

### 7.5 Managed role registry

Use a shared managed-role registry for bot-created roles:

- Guild ID.
- Discord role ID.
- Owner type: `reaction_panel`, `pulse_band`, or `pulse_reward`.
- Owner record ID.
- Generated name.
- Brand tag.
- Color.
- Symbol.
- Creation reason.
- Last synchronization status.
- Last synchronization error, nullable.
- Created and updated timestamps.

This registry prevents one feature from accidentally renaming or deleting a
role owned by another feature. Team roles and Team Leader roles remain outside
this registry because of the existing protected-role policy.

### 7.6 Audit records

Record at minimum:

- Welcome configuration created, edited, enabled, disabled, tested, and reset.
- Goodbye configuration created, edited, enabled, disabled, tested, and reset.
- Reaction-role panel created, edited, published, paused, resumed, and deleted.
- Role option added, removed, or changed.
- Custom reaction role created, renamed, recolored, synchronized, disabled, or
  deleted.
- Member role granted or removed by the panel.
- Single-choice replacement events.
- Failed actions and validation failures that require administrator attention.

Never store message content containing secrets or sensitive credentials.

---

## 8. Reliability and recovery

### 8.1 Startup recovery

On every startup:

1. Load community settings.
2. Validate configured channels.
3. Load reaction-role panels.
4. Re-register persistent views.
5. Verify panel messages still exist.
6. Re-render or mark missing panels for repair.
7. Validate role hierarchy.
8. Log a compact recovery summary.

Startup recovery must be idempotent. Running it multiple times must not duplicate panels, roles, reactions, or database rows.

### 8.2 Deleted resources

If an administrator deletes a configured channel, message, or role:

- Do not crash the bot.
- Mark the affected configuration as needing repair.
- Show a warning in the administrator status view.
- Offer a guided repair action.
- Do not silently create a replacement channel or role.

### 8.3 Interaction expiry

- Persistent member-facing controls must use stable custom IDs.
- Administrator wizard views may expire and should explain how to reopen them.
- Expired interactions must never produce an unhandled `Unknown interaction` error.
- Long operations should defer the response and then edit the original response.

### 8.4 Concurrency

Two rapid selections from the same single-choice group must not leave conflicting roles.

Use a per-member/per-group coordination strategy:

- Serialize role changes where practical.
- Re-read current member roles before applying the final change.
- Treat Discord’s final member role state as authoritative after the operation.
- Return one clear result to the member.

---

## 9. Permission model

### Administrators

Administrators may:

- Configure welcome and goodbye messages.
- Create and edit reaction-role panels.
- Choose eligible roles.
- Change group rules.
- Repair or delete panels.

### Members

Members may:

- View enabled panels.
- Select or remove eligible roles according to panel rules.

Members may not:

- Configure panels.
- Select protected roles.
- Use a panel to bypass Discord role hierarchy.
- Modify roles outside the configured panel.

### Bot permissions

The bot needs, where applicable:

- View channels.
- Send messages.
- Embed links.
- Add reactions.
- Read message history.
- Manage roles.
- Manage messages only if required for reaction cleanup or panel maintenance.

The setup flow should report missing permissions explicitly rather than failing later.

---

## 10. Visual and UX direction

Use a consistent visual language with the existing bot:

- Dark, professional tournament aesthetic.
- Short headings.
- Clear status badges.
- One primary action per screen.
- Ephemeral administrator controls.
- Live previews before publishing.
- Friendly but concise member confirmations.
- Consistent emojis:
  - `👋` Welcome
  - `🚪` Goodbye
  - `🎭` Reaction Roles
  - `✅` Enabled/success
  - `⏸` Paused
  - `⚠️` Needs attention
  - `✦` Independent role
  - `♛` Single-choice group or leader-style emphasis

Do not overload every message with decoration. The visual system should guide attention, not compete with the content.

---

## 11. Acceptance criteria

### Welcome

- An administrator can configure, preview, test, enable, disable, and reset a welcome message.
- A new member receives exactly one configured welcome message.
- Variables render correctly.
- Invalid channels and missing permissions are reported without crashing.
- Mentions are safe and controlled.
- Configuration persists across restarts.

### Goodbye

- An administrator can configure, preview, test, enable, disable, and reset a goodbye message.
- A departing member triggers exactly one configured goodbye message.
- Variables work without requiring the departed member to remain fetchable.
- The system handles deleted channels and missing permissions safely.
- Configuration persists across restarts.

### Reaction roles

- An administrator can create a panel without commands.
- A panel can contain independent roles and grouped roles.
- A group can enforce single choice.
- Selecting a new single-choice role removes only the previous role in that group.
- Selecting an independent role does not remove unrelated roles.
- Buttons, select menus, and emoji reactions work according to the panel’s configured mode.
- Members receive private confirmation.
- An administrator can create a custom bot-owned role directly from the panel wizard.
- Custom roles support configured names, brand tags, Unicode symbols, colors, and display settings.
- Existing administrator-created roles can be selected without being renamed or recolored.
- Bot-owned custom roles are renamed and recolored when the panel brand changes.
- The bot never deletes an administrator-created role through panel management.
- Unmanageable, missing, duplicate, or protected roles are rejected clearly.
- Panel messages and role rules survive bot restarts.
- Deleted messages, roles, or channels appear as repair warnings.
- Deleting a panel does not remove member roles by default.

### Existing behavior protection

- Team creation, editing, deletion, player management, and private-channel permissions continue to work.
- Team Leader roles remain outside automatic assignment/removal logic.
- No slash commands are added.
- All important changes are audit logged.

---

## 12. Recommended implementation order

1. Add database models and migration for community settings, panels, groups, and options.
2. Add shared message-template and validation services.
3. Add welcome and goodbye event listeners with idempotent sending and audit logging.
4. Add the Community Features administrator panel.
5. Implement reaction-role panel data and rendering.
6. Implement button and select-menu interactions.
7. Implement emoji-reaction synchronization.
8. Add startup recovery and repair status.
9. Add integration tests for permissions, single-choice replacement, deleted resources, and restarts.
10. Deploy behind the existing Railway workflow and verify logs before enabling the feature for the guild.

The implementation should favor a small number of reliable services over one large feature file. All Discord mutations should be explicit, validated, and wrapped with useful structured logs.
