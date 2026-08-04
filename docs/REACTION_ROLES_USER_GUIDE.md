# Reaction Roles: Administrator User Guide

## What this system does

The reaction-role system lets members choose server roles for themselves from a
published Discord panel. A panel is a permanent message containing a title,
instructions, and one or more role choices.

Members do not need to use slash commands. They use the controls shown on the
panel:

- Buttons.
- A select menu.
- Emoji reactions.

The administrator decides which format to use, which roles are available, and
whether members can choose one role or several roles from each group.

This guide explains how to configure and operate the system without requiring
any programming knowledge.

---

## Important vocabulary

### Panel

A **panel** is the published message that members interact with. It contains:

- A panel title.
- A description or instructions.
- Role choices.
- The selected presentation format.
- Optional role groups.

The panel has an administrator-facing name as well as a member-facing title.
The administrator name helps you identify the panel in the management screen;
the title and description are what members see.

### Role option

A **role option** is one selectable item inside a panel. Each option points to
one Discord role and can include:

- A member-facing label.
- A short description.
- An emoji.
- An optional group.
- A setting that determines whether the member may remove it.

The label shown on the panel does not have to be identical to the actual
Discord role name.

### Existing role

An **existing role** is a role that was already created in Discord. Adding it
to a panel does not make the bot the owner of that role.

Existing roles are protected by the bot:

- The bot can assign and remove the role when members use the panel.
- The bot does not rename the role through reaction-role branding.
- The bot does not recolor the role automatically.
- Removing the option does not delete the Discord role.

This is the safest choice when a role is already used by administrators,
moderation, permissions, or another system.

### Custom role

A **custom role** is created by the bot from inside the reaction-role editor.
The bot records that the role belongs to the panel and can later synchronize
its configured name and color.

When creating a custom role, the administrator can provide:

- Member-facing label.
- Discord role name.
- Brand tag or prefix.
- Unicode symbol.
- Color in hexadecimal format.

Custom roles created by this system are created as non-hoisted and
non-mentionable. They still need to be below the bot's highest role in the
Discord role list.

### Group

A **group** is a collection of role options that share a selection rule.

Examples:

- `Platform`: PC, Console, Mobile.
- `Notification type`: Announcements, Events, Tournaments.
- `Region`: Europe, North America, Asia.

A panel may contain:

- Independent options that are not in a group.
- One or more groups.
- A mixture of independent options and groups.

### Single choice

In a **single-choice** group, a member can hold only one role from that group
at a time.

For example, if a member chooses `PC`, then chooses `Console`, the bot removes
the PC role from that member and assigns Console. Roles outside that group are
not affected.

### Multiple choice

In a **multiple-choice** group, a member may hold several roles from that
group at the same time.

For example, a member could choose both `Tournament Updates` and `Event
Reminders`.

### Toggle policy

The toggle policy controls what happens when a member selects a role they
already have in a single-choice group:

- **Remove**: selecting the currently held role again removes it, leaving the
  member with no role from that group.
- **Strict**: selecting the currently held role again keeps it selected and
  tells the member that it is already selected.

---

## Before you begin

Make sure:

1. You are an administrator or have the bot's administrator access required by
   the Community Features panel.
2. The bot is in the server.
3. The bot can see the destination channel.
4. The bot can send messages and embeds in that channel.
5. The bot has **Manage Roles** permission.
6. The bot's highest role is above every role it must assign.
7. Any existing role you want to use is safe for members to receive.

Discord role hierarchy is especially important. A bot cannot assign or remove
a role that is above the bot's highest role, even if the bot has the Manage
Roles permission.

Do not put the Team Leader role into a reaction-role panel. Team Leader roles
are protected and are intended to be assigned manually by administrators.

---

## Opening reaction-role administration

1. Open the persistent administrator management panel.
2. Open **Community Features**.
3. Choose **Reaction Roles**.

The reaction-role administration screen shows existing panels and whether they
are ready or need repair. It also shows the panel's destination channel and
presentation mode.

Choose **Create Panel** to start a new panel.

---

## Creating a panel

Panel creation has two stages:

1. Choose the destination and presentation format.
2. Enter the panel's basic information.

### Stage 1: Choose a destination channel

Use the channel selector to choose where the published panel should appear.
Text channels and announcement/news channels are supported.

If no channel is selected, the system uses the channel where the setup flow was
opened when possible. It is still better to choose the destination explicitly,
especially when the administrator panel is private or located in a staff
channel.

The bot must be able to send and edit messages in the selected channel.

### Stage 1: Choose a presentation mode

Choose one of these formats:

1. **Buttons**
2. **Select menu**
3. **Emoji reactions**

The format affects how members interact with the panel. It does not change the
underlying roles, groups, or selection rules.

### Stage 2: Enter panel basics

Choose **Enter Panel Basics** and provide:

#### Panel name

This is the administrator reference name. Use a name that is easy to recognize,
such as:

- `Platform Roles`
- `Tournament Notifications`
- `Community Interests`
- `Server Region`

The panel name can be up to 100 characters.

#### Panel title

This is the heading members see on the published message. Keep it concise and
clear. It can be up to 256 characters.

Examples:

- `Choose your gaming platform`
- `Select the notifications you want`
- `Which events should we notify you about?`

#### Panel description

This is the member-facing instruction text. It can be up to 4,000 characters,
but shorter instructions are easier to read on mobile.

Explain:

- What the roles mean.
- Whether members may choose one or several.
- How to remove a choice.
- Who to contact if something is wrong.

Example:

> Choose the notifications you want to receive. You may select more than one.
> Use the same control again to remove a selection.

After submitting the basics, the panel is saved privately for administrators.
It is not visible to members until you publish it.

---

## Choosing the right presentation mode

### Buttons

Buttons display one button for each role option.

#### Best uses

Use buttons when:

- The panel has a small number of choices.
- You want the choices to be immediately visible.
- Members should be able to toggle roles quickly.
- The labels are short.

Examples:

- `PC`, `Console`, `Mobile`.
- `Announcements`, `Events`, `Giveaways`.
- `Europe`, `Americas`, `Asia`.

#### Member behavior

For ordinary independent options:

- Clicking a role the member does not have adds it.
- Clicking a role the member already has removes it if the option is removable.
- If the option is not removable, the bot explains that it cannot be removed.

For a single-choice group:

- Clicking a new choice removes the other role from that group.
- The selected role is then assigned.
- Roles outside that group remain untouched.
- Selecting the current role again follows the group's remove or strict policy.

#### Button capacity

The panel uses up to 20 button options. Discord also limits buttons to five
rows, with up to five buttons per row. If a panel needs more choices, a select
menu is usually the better format.

#### Strengths

- Fast for members.
- Very clear for small panels.
- Easy to understand on desktop and mobile.
- Good for independent yes/no-style role choices.

#### Limitations

- Too many options make the message crowded.
- A large role catalog may exceed the usable button layout.
- Members cannot search within buttons.

---

### Select menu

Select menus place role options inside a dropdown. Each group becomes its own
menu, while independent options are presented together in an ungrouped menu.

#### Best uses

Use select menus when:

- There are many role choices.
- You want grouped choices to be visually organized.
- You want a compact panel.
- Members should choose from a catalog rather than many visible buttons.

Examples:

- A list of languages.
- A large list of games.
- A region list.
- Several notification categories.

#### Member behavior

For a single-choice group, the menu allows one selection at a time. Selecting a
new option replaces the previous role in that group.

For a multiple-choice group, the menu allows several options from that group
to be selected together.

For independent options, members can choose multiple available options from
the ungrouped menu.

Select-menu selections are treated as explicit choices to add. To remove a
role, the member should use the relevant role control again if the panel
format and current Discord interaction allow it, or an administrator can
remove the role manually. A select menu is best when the main action is
choosing or changing preferences, rather than repeatedly toggling a small
number of roles.

#### Select-menu capacity

Each Discord select menu supports up to 25 options. Groups are separated into
their own menus, so splitting a large system into logical groups is useful.

#### Strengths

- Compact and mobile-friendly.
- Better for large lists.
- Supports grouped organization.
- Allows multiple selections in a multiple-choice group.

#### Limitations

- Members must open the menu to see choices.
- Very large lists still need to be split across groups or panels.
- The menu is less immediately visible than buttons.

---

### Emoji reactions

Emoji-reaction panels use a classic Discord message with one configured emoji
per role option. The bot adds the configured emojis to the panel message after
publishing.

#### Best uses

Use emoji reactions when:

- Your community already understands classic reaction roles.
- You want a simple, familiar experience.
- The choices are short and easy to represent with emoji.
- You want the panel to work without interactive buttons or menus.

Examples:

- `🎮 PC`, `🕹 Console`, `📱 Mobile`.
- `🔔 Announcements`, `🎉 Events`, `🏆 Tournaments`.

#### Member behavior

When a member adds the configured emoji, the corresponding role is assigned.
When the member removes their reaction, the corresponding role is removed.

For single-choice groups, the same group rules apply when the member adds a
new configured emoji:

- Other roles in that group are removed.
- The newly selected role is assigned.
- Roles outside the group are preserved.

#### Strengths

- Familiar to many Discord users.
- Visually simple.
- No button grid or dropdown is needed.

#### Limitations

- Emoji must be configured correctly.
- Custom emoji must remain available to the bot.
- The panel can become long when many options are added.
- Members must add and remove reactions manually.
- The bot must have permission to add reactions and read reaction events.

Use a select menu instead when the panel has many choices or when strict
grouped selection is the main goal.

---

## Adding role options

After creating the panel, the editor provides tools for adding role options.

### Selecting a group before adding an option

If the panel has groups, first use the group selector:

- Choose a specific group to place the next role into that group.
- Choose **No group** to create an independent option.

The selected group applies to the next role you add. Check the panel summary
after adding roles to confirm that each option is in the intended group.

### Adding an existing Discord role

Choose the existing-role selector and select the role.

The bot validates that the role is safe to manage. You may also provide:

- A member-facing label.
- A short description.
- An emoji.

If you do not provide a label, the role's current Discord name is used.

The role remains an administrator-owned Discord role. The reaction-role system
only uses it as an assignment target.

#### Existing-role safety

The bot will not safely manage roles that violate its hierarchy or protected
role rules. If the role cannot be assigned, move it below the bot's highest
role or choose a different role.

### Creating a custom role

Choose **Create Custom Role** and provide:

#### Member-facing label

The text members see in the panel. This can be friendlier than the actual
Discord role name.

#### Discord role name

The base name of the role in Discord.

#### Brand tag or prefix

An optional prefix used in the role's actual Discord name.

#### Unicode symbol

An optional symbol placed in the role's actual Discord name. Use a short,
readable symbol; overly decorative names can be difficult to search or read.

#### Color hex

Enter a six-digit hexadecimal color, such as:

- `#22D3EE` for cyan.
- `#8B5CF6` for violet.
- `#FACC15` for gold.

The leading `#` is accepted.

The bot creates the role, validates it, stores its configuration, and adds it
to the panel. The custom role is recorded as owned by that panel, which allows
later synchronization and rebranding.

The bot blocks custom role names or labels that attempt to create a Team
Leader role.

---

## Creating groups

Choose **Add Group** in the panel editor.

Provide:

### Group name

Use a short category name, such as:

- `Platform`
- `Notifications`
- `Region`
- `Game Mode`

The group name appears in the panel and in select-menu placeholders.

### Mode

Enter one of:

- `single`
- `multiple`

#### Choose `single` when

Members must choose exactly one category option at a time:

- One platform.
- One region.
- One primary team.
- One preferred language.

#### Choose `multiple` when

Members may choose several options:

- Several notification types.
- Several games.
- Several interests.
- Several event categories.

### Toggle policy

Enter one of:

- `remove`
- `strict`

#### Choose `remove` when

Members should be allowed to select their current single-choice role again to
remove it. This permits a member to end up with no role from that group.

#### Choose `strict` when

Members must always keep their current single-choice role until they choose a
different option. Selecting the current role again does not remove it.

After creating a group, select it before adding the role options that belong to
it.

---

## Independent roles versus grouped roles

### Independent role

An independent role has no group. It can be selected without affecting other
options in the panel.

Example:

- `Announcements`
- `Tournament News`
- `Giveaway Alerts`

A member may hold all of these independent roles if they choose them.

### Grouped role

A grouped role follows the group's selection rules.

Example:

`Platform` — single choice:

- PC
- Console
- Mobile

Choosing Console removes PC and Mobile if the member currently has them.

### Mixing both types

A single panel can contain:

- A single-choice Platform group.
- A multiple-choice Notifications group.
- Independent Community Events and Giveaway Alerts options.

The bot only changes roles inside the relevant group. It does not remove
unrelated roles.

---

## Publishing the panel

When all groups and role options are ready:

1. Review the panel summary.
2. Confirm the destination channel.
3. Confirm the presentation mode.
4. Check every label, emoji, description, and group.
5. Choose **Publish**.

Publishing does the following:

- Creates or updates the panel message.
- Adds the configured controls for buttons or select menus.
- Adds configured emoji reactions for reaction panels.
- Records the message so the bot can restore it after a restart.
- Repairs and synchronizes bot-owned custom roles before publishing.

Publishing the same panel again updates the existing panel message when it can
find it. It does not intentionally create a second copy.

---

## Pausing and resuming a panel

Use **Pause / Resume** in the panel editor.

### When paused

- The panel remains visible.
- Members should not receive normal role changes from that panel.
- The panel can be reviewed and edited by administrators.

### When resumed

- The panel becomes active again.
- Members can use its controls normally.

Pausing a panel does not remove roles that members already received.

---

## Rebranding custom roles

Select a role option in the editor, then choose **Rebrand Selected**.

This works only for bot-owned custom reaction roles. You can update:

- Discord role name.
- Brand tag.
- Unicode symbol.
- Color.

The bot synchronizes the Discord role and saves the new configuration.

Existing administrator-created roles cannot be rebranded through this control.
This protects roles that may be used by moderation, permissions, or other
server systems.

---

## Removing an option

Select the role option and choose **Remove Selected Option**.

You then choose how to handle it:

### Preserve Discord role

Removes the option from the panel but leaves the Discord role and existing
member assignments in place.

Use this when:

- The role may be used elsewhere.
- You may reuse it later.
- You are only changing the panel.

### Delete bot-owned role

Removes the option and deletes the bot-created Discord role. This is available
only for roles created by the reaction-role system.

Existing administrator-created roles are never deleted by this workflow.

---

## Deleting a panel

Choose **Delete Panel** and confirm the action.

Deleting a panel:

- Deletes the published panel message when possible.
- Removes the panel configuration.
- Preserves existing member roles by default.

For bot-owned custom roles, the confirmation flow can delete the panel-owned
roles if that option is selected. Use this carefully because deleting the
Discord roles can affect every member who has them.

Deleting the panel does not automatically remove existing roles from members
under the safe default.

---

## How role assignment works

When a member uses a valid control:

1. The bot checks that the panel and option are active.
2. The bot checks that the Discord role still exists.
3. The bot checks that the role is safe for the bot to manage.
4. The bot evaluates the option's group rules.
5. The bot adds, removes, or replaces the role.
6. The member receives a private confirmation.

The bot uses per-member processing locks so rapid repeated clicks are handled
in order instead of assigning conflicting choices at the same time.

The bot does not remove:

- Roles outside the selected group.
- Unconfigured roles.
- Protected Team Leader roles.
- Existing administrator roles simply because they are not in the panel.

---

## What members see

The published panel shows:

- The title.
- The description.
- Each enabled option.
- The option emoji when one is configured.
- The option description when one is configured.
- A group heading when options belong to a group.
- A `choose one` hint for single-choice groups.

Member confirmations are private. Other members do not see which role a user
just selected through the bot response.

---

## Permissions and Discord setup

### Bot permissions

The bot generally needs:

- View Channel.
- Send Messages.
- Embed Links.
- Read Message History.
- Add Reactions for emoji-reaction panels.
- Manage Roles.

For custom-role creation and custom-role synchronization, the bot must be able
to manage the target role according to Discord's role hierarchy.

### Role hierarchy

Move the bot's highest role above:

- Existing roles used in panels.
- Custom roles created by the bot.

Do not move the bot below roles it needs to assign. If the bot cannot manage a
role, the panel may publish but that option will be marked unavailable or need
repair when used.

### Team Leader protection

Team Leader roles are protected. Do not use reaction roles to distribute Team
Leader permissions or leadership roles. Administrators must manage Team Leader
assignment manually.

---

## Panel limits and practical recommendations

Discord imposes limits on interactive components. The system follows these
practical limits:

- Buttons: up to 20 displayed role options.
- Select menus: up to 25 options per menu.
- Panel and option labels: keep them short enough to read comfortably.
- Panel title: up to 256 characters.
- Panel description: up to 4,000 characters.
- Panel administrator name: up to 100 characters.
- Option label: up to 100 characters.
- Option description: up to 100 characters.
- Group name: up to 100 characters.

Recommendations:

- Use buttons for roughly 2–10 highly visible choices.
- Use select menus for larger lists.
- Split unrelated systems into separate panels.
- Use groups for rules, not decoration.
- Keep the panel description short.
- Use consistent emoji and naming across related panels.
- Do not put every server role into one enormous panel.

---

## Common setup examples

### Example 1: Gaming platform

Create one panel:

- Mode: Buttons.
- Group name: `Platform`.
- Group mode: `single`.
- Toggle: `remove`.

Add:

- 🎮 PC
- 🕹 Console
- 📱 Mobile

Result: members may hold one platform role and can remove it by selecting the
current role again.

### Example 2: Notifications

Create one panel:

- Mode: Select menu.
- Group name: `Notifications`.
- Group mode: `multiple`.
- Toggle: `remove`.

Add:

- 🔔 Announcements.
- 🎉 Events.
- 🏆 Tournament Updates.
- 🎁 Giveaways.

Result: members can subscribe to several notification categories.

### Example 3: Region plus independent alerts

Create one panel with:

`Region` group:

- Mode: `single`.
- Options: Europe, Americas, Asia.

Independent options:

- Tournament Alerts.
- Community Events.

Result: members choose one region while independently opting into either or
both alert roles.

### Example 4: Classic emoji roles

Create one panel:

- Mode: Emoji reactions.
- No group, or a single-choice group if the emojis represent alternatives.

Add:

- 🎮 PC.
- 🕹 Console.
- 📱 Mobile.

Result: adding an emoji assigns the role and removing the emoji removes it.

---

## Troubleshooting

### The panel will not publish

Check:

- The destination channel still exists.
- The bot can send messages there.
- The bot can embed links.
- The bot can read message history.
- The selected channel is a text or announcement channel.

### A role option says it is unavailable

Check:

- The Discord role still exists.
- The role is below the bot's highest role.
- The bot has Manage Roles.
- The role is not protected.
- The panel is enabled.

The panel may be marked as needing repair when a channel, message, or role is
missing.

### A member cannot receive a role

The most common cause is role hierarchy. Move the bot's role above the target
role, then publish or use the panel again.

Also check whether the target role has permissions that should not be
self-assignable. Existing roles are deliberately validated before use.

### A single-choice group still has an unexpected role

Confirm that both roles are assigned to the same group. Roles from different
groups, different panels, or independent options are not automatically
removed.

### A member wants to remove a role

For buttons, selecting an active removable role again toggles it off. For
single-choice groups with strict mode, the member must choose another role or
ask an administrator to remove the current role.

For emoji panels, removing the member's reaction removes the corresponding
role.

### The panel message disappeared

Open the reaction-role administrator screen and inspect the panel status. The
panel can be published again after confirming the destination channel and
roles.

### A custom role name or color did not update

Only bot-owned custom reaction roles can be rebranded automatically. Existing
administrator-created roles are intentionally protected from automatic rename
and recolor operations.

### Emoji reactions do not work

Check:

- The panel was created in Emoji reactions mode.
- Every option has an emoji.
- The bot can add reactions.
- The bot can read message history and reaction events.
- The configured emoji is still valid.

---

## Recommended administrator workflow

For a reliable production panel:

1. Decide whether members need one choice or several.
2. Create a separate panel for each unrelated topic.
3. Choose buttons for small visible lists.
4. Choose select menus for larger lists.
5. Choose emoji reactions only when the community prefers that style.
6. Create groups before adding grouped options.
7. Use existing roles when another system or staff manages the role.
8. Use custom roles when the panel should own the role's name and color.
9. Test every option with a non-administrator test account.
10. Check that single-choice replacement removes only the intended role.
11. Publish in a channel members can see.
12. Keep the administrator panel private.
13. Recheck role hierarchy after adding or rearranging server roles.

---

## Safety summary

The reaction-role system is designed to be conservative:

- Existing roles are not renamed or recolored automatically.
- Existing roles are not deleted through panel deletion.
- Bot-owned custom roles can be synchronized and rebranded.
- Team Leader roles are protected.
- Single-choice replacement is limited to the configured group.
- Pausing a panel does not strip roles from members.
- Deleting a panel preserves member roles by default.
- A missing role or inaccessible role is reported rather than silently
  replaced.

When in doubt, use **Preserve Discord Role** and change the panel configuration
instead of deleting a Discord role.