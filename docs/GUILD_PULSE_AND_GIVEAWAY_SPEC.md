# Guild Pulse Progression & Giveaways
## Product and Technical Specification

**Status:** Proposed  
**Audience:** Product, design, and implementation teams  
**Design direction:** An original, premium Discord experience with a strong visual identity, not a copy of Arcane or any other leveling bot.

---

## 1. Purpose

Add two major community systems to the bot:

1. **Guild Pulse** — an original XP, level, identity, milestone, and leaderboard system that rewards meaningful participation without turning the server into a noisy grind.
2. **Giveaway Operations** — a fully managed giveaway lifecycle that handles setup, eligibility, entries, scheduled ending, winner selection, claims, rerolls, and auditability.

The bot conducts giveaways but does **not** supply, purchase, transfer, verify, or distribute prizes. The server owner or organizer is responsible for the prize and fulfillment.

Both systems must:

- Use the existing UI-driven Discord architecture.
- Be configured through the persistent management panel, buttons, modals, and select menus.
- Avoid slash commands.
- Persist safely in PostgreSQL.
- Recover cleanly after restarts.
- Provide polished member-facing embeds and private interaction feedback.
- Remain understandable to administrators without technical knowledge.

Existing team-management behavior must remain intact:

- The bot may create Team Leader roles.
- The bot must never assign, remove, transfer, or otherwise manage Team Leader roles.
- Level rewards, reaction roles, giveaway eligibility, and other new systems must never modify Team Leader roles.

---

## 2. Product vision

### 2.1 Guild Pulse

Guild Pulse should make a member feel that their participation has a visible shape:

- They can see where they currently stand.
- They can understand how they progressed.
- They can see the next meaningful milestone.
- They can compare themselves with the community without the server feeling like a spreadsheet.
- They can earn recognition without being pushed to spam messages.

The central experience is not “send messages to gain points.” It is:

> **Participate meaningfully, build your presence, and watch your place in the guild evolve.**

### 2.2 Giveaway Operations

Giveaways should feel trustworthy and organized rather than improvised:

- Members know exactly how to enter.
- Eligibility is visible before entry.
- The bot prevents duplicate entries.
- Closing and winner selection happen predictably.
- Winners can claim through a clear workflow.
- Administrators can reroll or cancel with an audit trail.
- The prize responsibility remains explicitly with the organizer.

---

## 3. Experience architecture

### 3.1 Management panel additions

Add a new top-level button to the existing persistent management panel:

**`✦ Community Systems`**

This opens an ephemeral administrator hub with:

- **`◈ Guild Pulse`**
- **`🎁 Giveaways`**
- **`📊 Activity & Health`**

The hub displays concise status:

```text
Guild Pulse       ✅ Active · 184 members tracked · Leaderboard refreshed 3m ago
Giveaways         ✅ 1 live · 4 scheduled
System health     ✅ No repair warnings
```

Only administrators may open or use configuration controls.

### 3.2 Member-facing entry points

The first implementation should support persistent, configurable messages for:

- Member progress card.
- Leaderboard card.
- Milestone announcement.
- Giveaway panel.

The bot should not require a command for ordinary use. Members interact with buttons and select menus attached to messages.

Recommended member buttons:

- **`📈 My Pulse`**
- **`🏆 Leaderboard`**
- **`🎁 Giveaway details`**
- **`🎟 Enter giveaway`**

These can be placed in separate messages or combined into a configured community hub.

---

# Part I — Guild Pulse Progression

## 4. Guild Pulse concept

### 4.1 Original progression model

Guild Pulse uses three connected but distinct values:

1. **Pulse XP** — the member’s accumulated progression score.
2. **Current Level** — the member’s visible progression step.
3. **Presence** — a non-competitive activity summary showing the member’s recent consistency and contribution shape.

Presence is not another currency. It is a visual summary generated from recent activity:

- Conversation.
- Helpful reactions.
- Voice participation.
- Community events.
- Streak continuity, if enabled.

This lets the member profile feel alive without creating a complicated second progression system.

### 4.2 Progression identity

Each guild may choose a theme name for levels:

- Default: **Pulse**
- Optional administrator label: **Path**, **Momentum**, **Signal**, or a custom name

The underlying behavior remains the same. The label changes presentation only.

Example:

```text
Pulse Level 18
1,840 / 2,250 XP to Level 19
Next milestone: Level 20 · Community Voice
```

### 4.3 Level curve

Use a predictable, transparent curve:

```text
xp_required_for_level(level) =
    round(100 * level ** 1.55)
```

The implementation should store total XP and calculate the current level from the configured curve. It should not store level as the only source of truth.

Guild administrators may choose one of three pacing presets:

- **Relaxed:** lower XP requirements and slower decay of anti-spam eligibility.
- **Balanced:** recommended default.
- **Ambitious:** higher requirements for long-running communities.

The preset changes the multiplier, not the fundamental formula:

```text
required_xp = round(base_curve(level) * pacing_multiplier)
```

The maximum level should be configurable, with a safe default of 100. If a member exceeds the maximum, excess XP remains stored.

### 4.4 Level bands

Level bands provide identity without replacing the numeric level:

| Levels | Default band |
|---:|---|
| 1–4 | New Signal |
| 5–9 | Active Presence |
| 10–19 | Familiar Voice |
| 20–34 | Community Pillar |
| 35–49 | Trusted Core |
| 50–74 | Guild Beacon |
| 75–99 | Inner Circle |
| 100+ | Legacy Signal |

Administrators may rename bands and assign presentation colors. Band changes must not alter XP.

---

## 5. XP sources

### 5.1 Configurable sources

Guild Pulse supports these sources independently:

1. **Meaningful text participation**
2. **Voice participation**
3. **Helpful reactions**
4. **Community events**
5. **Manual administrator awards**

Each source can be enabled, disabled, or weighted by administrators.

### 5.2 Text participation

A qualifying message awards XP only when it passes all configured checks:

- Minimum character count, default 12.
- Maximum message XP frequency, default one award per 60 seconds.
- Channel eligibility.
- Not a bot message.
- Not a webhook message.
- Not a repeated or near-duplicate message.
- Not a message containing only mentions, emojis, or links unless the administrator allows it.

Recommended default:

```text
Base message award: 8 XP
Cooldown: 60 seconds per member
Daily soft cap: 600 XP from messages
```

The cooldown is per member, not global. The bot must not reveal the exact anti-spam thresholds to members.

### 5.3 Voice participation

Voice XP should reward active participation, not silent idling:

- The member must be in a configured eligible voice channel.
- The member must not be deafened by the server or self-deafened.
- The member must not be alone unless solo voice XP is explicitly enabled.
- XP is awarded in time blocks, default every 5 minutes.
- AFK channels are excluded by default.

Recommended default:

```text
6 XP per eligible 5-minute block
Daily soft cap: 480 XP from voice
```

The bot should periodically re-check voice state and not rely only on join/leave events.

### 5.4 Helpful reactions

Reactions may award limited XP when a member reacts to a non-bot message in an eligible channel.

Safeguards:

- One XP award per message per member.
- No XP for reacting to the member’s own message.
- Daily cap.
- Optional allow-list of reaction emojis.
- No XP farming through rapid add/remove cycles.

Recommended default:

```text
1 XP per qualifying reaction
Daily cap: 50 XP
```

### 5.5 Community events

Events may award XP through administrator-controlled buttons or event completion records.

Examples:

- Tournament participation.
- Scheduled community night.
- Verified challenge completion.
- Team event attendance.

This source must always be administrator-controlled. The bot must not infer prize eligibility or event completion from arbitrary messages.

### 5.6 Manual awards

Administrators may award or subtract Pulse XP through a private UI:

- Select member.
- Enter XP amount.
- Enter a required reason.
- Review.
- Confirm.

Every manual change must be audit logged. The UI must clearly distinguish an XP adjustment from a role assignment.

---

## 6. Anti-abuse and fairness

### 6.1 General principles

The system should reward consistency and meaningful activity, not volume alone.

Never use punitive hidden XP deductions as the first response to suspected abuse. Prefer:

- Cooldowns.
- Caps.
- Eligibility filters.
- Duplicate detection.
- Channel configuration.
- Transparent status warnings for administrators.

### 6.2 Message similarity

Detect likely farming through:

- Exact repeated content.
- Very short repeated patterns.
- High-frequency message bursts.
- Repeated messages across multiple channels in a short window.

The bot may suppress XP for suspicious messages while leaving the message untouched.

### 6.3 Self-farming protections

Do not award XP for:

- Bot-to-bot interactions.
- Webhook messages.
- Self-reactions.
- Reactions to bot messages unless explicitly allowed.
- Rapid role or giveaway interactions.

### 6.4 Recalculation and corrections

All XP grants should be recorded as ledger events rather than only incrementing a total:

- Source.
- Amount.
- Reason.
- Message/event reference where applicable.
- Timestamp.
- Whether the event was later reversed.

Administrators may request a recalculation for a member or the whole guild. Recalculation must be an explicit, deferred operation with progress logging.

---

## 7. Member progress experience

### 7.1 My Pulse card

The member-facing progress card should include:

- Display name and avatar.
- Current level.
- Level band.
- Progress bar.
- Current XP and next-level requirement.
- XP earned in the last 7 days.
- Current rank.
- Recent activity mix.
- Next milestone.

Example:

```text
YOUR PULSE
Level 18 · Community Pillar

██████████████░░░░  1,840 / 2,250 XP

Rank #24 of 184
Last 7 days: 312 XP
Text  ████████  Voice  ███  Events  ██

Next milestone
Level 20 · unlocks the Community Voice role
```

The activity bars are a presentation summary, not a second points system.

### 7.2 Progress history

The card should offer a private **`🕒 History`** view:

- Recent level-ups.
- Recent XP sources.
- Manual adjustments.
- Reversed or corrected events.

Do not expose exact activity moderation flags to the member.

### 7.3 Level-up moment

When a member levels up:

1. Create a level-up record.
2. Optionally send a configured public announcement.
3. Send a private confirmation.
4. Apply eligible level reward roles.
5. Log the event.

Public announcements should be configurable:

- Disabled.
- Every level.
- Milestone levels only.
- Quiet channel only.

The default should be milestone-only to avoid channel noise.

### 7.4 Reward roles

Administrators may map levels or bands to reward roles.

The bot may:

- Assign configured progression reward roles.
- Remove older mutually exclusive progression roles if configured.

The bot must never:

- Assign or remove Team Leader roles.
- Modify roles not explicitly configured as progression rewards.
- Move roles in the Discord hierarchy.

Role validation must happen before saving and again before assignment.

---

## 8. Leaderboard design

### 8.1 Leaderboard purpose

The leaderboard should be a living community display, not a raw database dump.

It should show:

- Top members by Pulse XP.
- Current level and band.
- Recent movement.
- The viewer’s own rank even if they are not in the top list.
- Last refresh time.
- Season or all-time scope.

### 8.2 Display format

Recommended public leaderboard embed:

```text
◈ GUILD PULSE · TOP 10
Updated 4 minutes ago · Balanced pace · Season 3

1  🥇 Nova        Level 42 · +2 today
2  🥈 Kairo       Level 39 · +0 today
3  🥉 Mira        Level 37 · +1 today
4  4  Rowan       Level 35 · +3 today
...

Your position: #24 · Level 18
```

Use compact styling, strong spacing, and a stable message rather than sending a new message every refresh.

### 8.3 Refresh requirement

The leaderboard should refresh every 5 minutes by default and never intentionally exceed 10 minutes under normal operation.

Implementation strategy:

1. Maintain a cached leaderboard snapshot per guild and scope.
2. Mark a guild leaderboard dirty when XP changes materially.
3. Run a scheduler every 60 seconds.
4. Refresh dirty leaderboards when their minimum update interval has elapsed.
5. Refresh all active leaderboards at least every 5 minutes.
6. Skip Discord edits when the rendered content has not changed.
7. Respect Discord rate limits and retry with backoff.

The exact target is:

```text
Normal operation: 5-minute refresh
Maximum intended age: 10 minutes
Temporary Discord outage: show last successful refresh time
```

### 8.4 Ranking rules

Default ordering:

1. Total Pulse XP descending.
2. Current level descending.
3. Earlier achievement of the current XP total.
4. Stable member ID as final deterministic tie-breaker.

Do not use random tie-breaking.

### 8.5 Leaderboard scopes

Support:

- All-time.
- Current season.
- Last 7 days.
- Last 30 days.

The first implementation may publish one configured public scope and allow other scopes through a private member view.

### 8.6 Seasons

Seasons are optional and should not erase historical data.

A season has:

- Name.
- Start time.
- End time, optional.
- XP scope.
- Whether reward roles are awarded at close.

When a season ends:

- Freeze its snapshot.
- Archive standings.
- Start the next season only through administrator confirmation.
- Preserve all-time XP separately.

---

## 9. Guild Pulse administration

### 9.1 Setup home

The admin home should show:

```text
GUILD PULSE
Status: Active
Pace: Balanced
Tracked members: 184
Leaderboard: #pulse-leaderboard · refreshed 4m ago
Last level-up: 6m ago

XP sources
✅ Text   ✅ Voice   ⏸ Reactions   ✅ Events
```

Actions:

- `⚙ Configure`
- `🧪 Preview`
- `🏆 Leaderboard`
- `🎖 Rewards`
- `🗓 Seasons`
- `🧹 Recalculate`
- `⏸ Pause XP`

### 9.2 Configuration wizard

The wizard should use progressive disclosure:

1. Choose pacing preset.
2. Choose enabled XP sources.
3. Configure channels and caps.
4. Configure announcement behavior.
5. Configure reward roles.
6. Preview.
7. Confirm.

Advanced settings should be hidden behind **`More controls`**.

### 9.3 Safe pause behavior

When paused:

- No new XP is awarded.
- Existing member data remains visible.
- Leaderboard continues to show the last valid snapshot.
- Administrators can still edit configuration and run reports.
- Members see a concise paused status rather than an error.

---

# Part II — Giveaway Operations

## 10. Giveaway principles

### 10.1 Scope

The bot manages the mechanics of a giveaway:

- Configuration.
- Publication.
- Eligibility.
- Entry collection.
- Duplicate prevention.
- Scheduled closing.
- Winner selection.
- Claim window.
- Rerolls.
- Cancellation.
- Logs and status.

The bot does **not**:

- Buy the prize.
- Hold the prize.
- Transfer money or goods.
- Verify delivery.
- Guarantee the organizer will fulfill the prize.
- Resolve disputes outside the Discord workflow.

Every public giveaway message must state that the organizer is responsible for prize fulfillment.

### 10.2 Giveaway lifecycle

State machine:

```text
DRAFT
  -> SCHEDULED
  -> LIVE
  -> ENDING
  -> WINNER_PENDING_CLAIM
  -> COMPLETED

Any active state may become:
  -> PAUSED
  -> CANCELLED
  -> FAILED_REPAIR
```

Rerolls create a new winner-selection event while preserving the original draw.

### 10.3 Giveaway types

Support two entry styles:

1. **Button entry** — recommended default.
2. **Emoji reaction entry** — optional compatibility mode.

The underlying entry record is the same. A member can have at most one active entry per giveaway.

---

## 11. Giveaway creation flow

### 11.1 Admin dashboard

The giveaway dashboard displays:

```text
GIVEAWAYS
Live       1
Scheduled  4
Completed  28
Needs care 0

Actions:
🎁 Create Giveaway
📋 Manage Live
🗂 History
⚙ Defaults
```

### 11.2 Step 1: Prize information

The organizer enters:

- Prize title.
- Public prize description.
- Quantity or number of winners.
- Optional approximate value, clearly labeled as organizer-provided.
- Organizer or sponsor name.
- Prize fulfillment note.

The bot must show a confirmation:

```text
The bot only conducts this giveaway. The organizer remains responsible
for providing and delivering the prize.
```

The bot must not present itself as the prize provider.

### 11.3 Step 2: Schedule

Fields:

- Entry channel.
- Start time, default immediately.
- End time or duration.
- Time zone display.
- Claim window.

Store all timestamps in UTC and render them using Discord relative and absolute timestamps:

```text
Ends <t:...:R> · <t:...:F>
```

Validate:

- End is after start.
- Claim window is positive.
- Duration is within configured limits.
- The bot can access the channel.

### 11.4 Step 3: Eligibility

Eligibility rules are explicit and previewable:

- Minimum account age.
- Minimum server membership age.
- Required role(s).
- Excluded role(s).
- Required Pulse level, optional.
- Required channel access.
- Whether organizers/staff are eligible.
- Whether bots are excluded.
- Optional prior-giveaway cooldown.

For role logic:

- Required roles may use `ANY` or `ALL`.
- Excluded roles always override required roles.
- The bot must never grant a missing eligibility role.
- Eligibility is checked at entry and again before drawing.

Do not make message activity a hidden requirement.

### 11.5 Step 4: Entry limits and extras

Default:

- One entry per member.
- No paid entries.
- No hidden bonus entries.

Optional organizer-controlled features:

- Extra entries for a configured role.
- Extra entries for a verified event completion.
- Extra entries for a Pulse level.

If enabled, the public message must show the rule plainly. The bot must show a member their entry count privately.

The first release should keep the default simple and make extra entries opt-in.

### 11.6 Step 5: Presentation

Fields:

- Embed color.
- Title.
- Description.
- Image or thumbnail.
- Footer.
- Entry button label.
- Optional organizer note.

The bot provides polished templates:

1. **Clean draw**
2. **Tournament reward**
3. **Community celebration**
4. **Sponsor spotlight**

Templates change presentation only, not rules.

### 11.7 Step 6: Preview and publish

Before publishing, show:

- Rendered giveaway message.
- Eligibility summary.
- Start/end times.
- Winner count.
- Claim deadline.
- Organizer responsibility note.

Actions:

- `← Back`
- `🧪 Send test`
- `✅ Publish`
- `✕ Cancel`

Publishing must be idempotent. A repeated interaction must not create multiple giveaway records or duplicate public messages.

---

## 12. Member giveaway experience

### 12.1 Public panel

Recommended public message:

```text
🎁 COMMUNITY GIVEAWAY
Premium Tournament Bundle

A community giveaway organized by @Organizer.

🏆 Winners: 2
🎟 Entries: 87
⏱ Ends in 2 hours
📌 Eligibility: Level 10+ and Tournament Members

The bot conducts the draw only. The organizer is responsible for the prize.

[🎟 Enter Giveaway] [📋 View Rules]
```

### 12.2 Entry action

When a member selects **Enter Giveaway**:

1. Defer if eligibility checks may take time.
2. Evaluate eligibility.
3. Check giveaway state.
4. Check duplicate entry.
5. Store the entry idempotently.
6. Return a private confirmation.

Success:

```text
✅ Entry confirmed.
Your entry number: 87
Winners: 2 · Ends in 2 hours
```

Ineligible:

```text
⚠️ You are not eligible for this giveaway.
Required: Pulse Level 10+ and the Tournament Member role.
```

Already entered:

```text
ℹ️ You are already entered.
Your entry count: 1
```

### 12.3 View rules

The rules view must show:

- Prize description.
- Number of winners.
- Exact end time.
- Eligibility rules.
- Extra-entry rules, if any.
- Claim deadline.
- Organizer responsibility statement.
- Cancellation/reroll policy.

Do not hide important conditions inside an external URL.

### 12.4 Leave and rejoin behavior

Default:

- A member who leaves is no longer eligible at draw time.
- Their historical entry remains stored for audit.
- If they rejoin before the draw, eligibility is evaluated again.
- The system should not silently recreate an entry if the original giveaway was configured as one-entry-only; it may preserve the original entry record and mark it revalidated.

The administrator may choose a stricter “must remain in server continuously” policy.

---

## 13. Drawing and winner management

### 13.1 Closing

At end time:

1. Move giveaway to `ENDING`.
2. Stop new entries.
3. Re-evaluate all entries.
4. Remove entries that no longer meet eligibility.
5. Build the final eligible pool.
6. Select winners.
7. Create a draw record.
8. Publish the winner announcement.
9. Start claim timers.

If the bot is offline at the scheduled end, it must finalize overdue giveaways during startup recovery.

### 13.2 Fair selection

The draw must be reproducible and auditable.

Recommended method:

1. Create a cryptographically secure random draw seed at closing time.
2. Store the seed hash before selection.
3. Sort eligible entries deterministically by entry ID.
4. Use a secure seeded selection method without replacement.
5. Store the resulting winner order and final eligible count.
6. Reveal the seed after the draw is published if the implementation supports public verification.

Never use message order or Discord user ID alone as the random source.

### 13.3 Winner announcement

The public announcement should include:

- Giveaway title.
- Winner mentions, if mentionable.
- Claim deadline.
- Private claim action.
- Organizer responsibility reminder.
- Final eligible entry count.

Example:

```text
🎉 GIVEAWAY COMPLETE

Congratulations to:
@Nova
@Mira

Winners must claim within 24 hours using the button below.
The organizer is responsible for providing the prize.

Eligible entries at draw: 104
```

### 13.4 Claim flow

The winner selects **Claim Prize**:

1. The bot confirms they are the selected winner.
2. The bot records claim time.
3. The bot asks for a private confirmation that they understand the organizer will fulfill the prize.
4. The bot marks the winner as claimed.
5. The bot notifies the organizer through a private administrator view or configured staff channel.

The bot must not collect sensitive payment information, addresses, passwords, tokens, or private keys.

If contact details are needed, direct the organizer and winner to their existing trusted process; do not store sensitive data in the bot database.

### 13.5 Unclaimed winners

When a claim deadline expires:

- Mark the winner as expired.
- Show administrators the pending action.
- Offer:
  - `🔁 Reroll expired winner`
  - `✅ Mark fulfilled manually`
  - `🛑 Cancel remaining prize`

The bot must never automatically declare a prize fulfilled.

### 13.6 Rerolls

A reroll must:

- Exclude already selected winners unless the administrator explicitly allows a replacement of the same winner.
- Re-evaluate eligibility.
- Create a new draw record.
- Preserve the original draw and reason.
- Publish a clear reroll announcement.
- Reset the claim deadline only if the administrator chooses that option.

Reroll reasons:

- Winner did not claim.
- Winner became ineligible.
- Organizer-approved replacement.

---

## 14. Giveaway administration

### 14.1 Live giveaway dashboard

For each live giveaway show:

```text
Premium Tournament Bundle
Status: LIVE
Ends in: 1h 42m
Entries: 87
Eligible now: 84
Winners: 2
Channel: #giveaways
Health: ✅
```

Actions:

- `✏️ Edit presentation`
- `📋 View rules`
- `👥 View eligibility`
- `⏸ Pause entries`
- `▶ Resume entries`
- `⏹ End now`
- `🛑 Cancel`

Rules that affect fairness, including eligibility, winner count, and end time, should require a confirmation and be audit logged.

### 14.2 Cancellation

Cancellation must require:

- Reason.
- Confirmation.

Public cancellation message:

```text
🛑 Giveaway cancelled by the organizer.
No prize has been distributed by the bot.
```

Cancellation does not delete entry history.

### 14.3 Manual close

Administrators may end a giveaway early. The UI must show:

- Current entry count.
- Current eligible count.
- Time remaining.
- Warning that ending now begins the draw immediately.

### 14.4 History and audit

Giveaway history should show:

- Created time.
- Organizer.
- Start/end times.
- Entry count.
- Eligible count.
- Draw seed hash.
- Winner order.
- Claim states.
- Rerolls.
- Cancellation or failure reasons.

No secret or sensitive winner contact data should be stored.

---

## 15. Data model

Names may follow existing SQLAlchemy conventions, but the following concepts are required.

### 15.1 Guild Pulse settings

- Guild ID.
- Enabled.
- Display name.
- Pacing preset.
- Maximum level.
- Enabled XP sources.
- Source configuration JSON.
- Leaderboard channel ID.
- Leaderboard message ID.
- Leaderboard scope.
- Leaderboard refresh interval.
- Announcement channel ID.
- Announcement mode.
- Current season ID.
- Updated by and timestamp.

### 15.2 Member progression

- Guild ID.
- Discord member ID.
- Total XP.
- Current season XP, if using seasons.
- Current level cache.
- Last activity timestamp.
- Last leaderboard rank.
- Seven-day XP cache or computed aggregate.
- Created and updated timestamps.

Total XP remains the source of truth; level and rank are derived or safely cached values.

### 15.3 XP ledger

- Guild ID.
- Member ID.
- Amount.
- Source.
- Source reference.
- Idempotency key.
- Reversal reference, nullable.
- Reason.
- Created timestamp.

Unique idempotency keys prevent duplicate awards when Discord events are delivered more than once.

### 15.4 Seasons

- Guild ID.
- Name.
- Start time.
- End time.
- Status.
- Finalized snapshot reference.
- Created by.

### 15.5 Progression rewards

- Guild ID.
- Level or band threshold.
- Discord role ID.
- Mutually exclusive group, nullable.
- Enabled state.

Team Leader roles must be rejected during validation and must not be stored as progression rewards.

### 15.6 Giveaway

- Guild ID.
- Public channel ID.
- Public message ID.
- Internal title.
- Prize description.
- Organizer ID.
- Status.
- Start time.
- End time.
- Claim window.
- Winner count.
- Entry mode.
- Eligibility configuration JSON.
- Presentation configuration JSON.
- Organizer-responsibility acknowledgement.
- Created and updated timestamps.

### 15.7 Giveaway entry

- Giveaway ID.
- Guild ID.
- Member ID.
- Entry count or weight.
- Eligibility status.
- Eligibility failure reason, nullable.
- Entered timestamp.
- Last revalidated timestamp.
- Unique `(giveaway_id, member_id)` constraint for the default one-entry mode.

### 15.8 Giveaway draw

- Giveaway ID.
- Draw number.
- Draw time.
- Eligible entry count.
- Winner order JSON.
- Seed hash.
- Reveal seed, if supported.
- Draw reason.
- Created by or system actor.

### 15.9 Giveaway winner

- Draw ID.
- Giveaway ID.
- Member ID.
- Winner position.
- Claim status.
- Claim deadline.
- Claimed timestamp.
- Expired timestamp.
- Reroll replacement reference.

---

## 16. Scheduling and reliability

### 16.1 Scheduler

Use one managed scheduler task per bot process rather than spawning an unbounded task for every guild.

The scheduler handles:

- XP voice intervals.
- Leaderboard refresh.
- Scheduled giveaway starts.
- Giveaway endings.
- Claim deadline reminders.
- Overdue recovery.

Each job must be idempotent and safe to run again.

### 16.2 Leaderboard freshness

Target:

- Refresh every 5 minutes.
- Never intentionally older than 10 minutes.

When Discord rate limits or temporarily fails:

- Keep the last successful message.
- Store `last_attempt_at` and `last_success_at`.
- Show the last successful time.
- Retry with bounded exponential backoff.
- Avoid flooding the channel with new messages.

### 16.3 Giveaway recovery

On startup:

1. Load all non-terminal giveaways.
2. Start giveaways whose start time has passed.
3. End giveaways whose end time has passed.
4. Resume claim timers.
5. Verify public messages.
6. Re-register buttons and select views.
7. Mark missing messages or channels as `FAILED_REPAIR`.
8. Log a compact recovery summary.

### 16.4 Event idempotency

Discord events may be duplicated or arrive out of order. Use:

- Stable event IDs where available.
- Idempotency keys for XP awards.
- Unique database constraints for entries.
- State checks before giveaway transitions.
- Transaction boundaries around draw creation and winner selection.

---

## 17. Permissions and safety

### 17.1 Administrator permissions

Administrators may:

- Configure Guild Pulse.
- Adjust XP settings.
- Assign configured progression reward roles.
- Create and manage giveaways.
- Reroll or cancel giveaways.
- View audit history.

### 17.2 Member permissions

Members may:

- View their progress.
- View leaderboards.
- Enter eligible giveaways.
- Claim a selected giveaway.

Members may not:

- Modify XP.
- Change eligibility.
- Create giveaways.
- Select or alter progression reward roles outside configured behavior.

### 17.3 Bot permissions

Depending on enabled features:

- View channels.
- Send messages.
- Embed links.
- Read message history.
- Manage roles for explicitly configured progression rewards.
- Add reactions for optional giveaway entry mode.
- Manage messages only when explicitly required by panel maintenance.

The setup UI must show missing permissions before activation.

### 17.4 Protected resources

The bot must reject:

- `@everyone`.
- Managed integration roles.
- Roles above or equal to the bot’s highest role.
- Team Leader roles.
- Roles not belonging to the current guild.
- Deleted or inaccessible channels.

---

## 18. Visual and UX direction

### 18.1 Guild Pulse aesthetic

Use an original visual language:

- Deep midnight background.
- Electric cyan for active progress.
- Warm gold for milestones.
- Violet for long-term status.
- Coral for warnings.
- Soft gradients in embeds only where Discord renders them clearly.

Suggested symbols:

- `◈` Pulse identity.
- `↗` recent movement.
- `◆` milestone.
- `◌` activity.
- `⌁` season.
- `▰` progress bar.

Avoid copying familiar leveling-bot phrases or layouts. The product should feel like a purpose-built community identity system.

### 18.2 Giveaway aesthetic

Use a more celebratory but controlled style:

- Gold or coral accent for live giveaways.
- Green only for confirmed claims.
- Neutral gray for scheduled and completed states.
- Red reserved for cancellation or failed repair.

Every giveaway embed must visually separate:

1. Prize information.
2. Entry action.
3. Eligibility.
4. Timing.
5. Organizer responsibility.

### 18.3 Interaction feedback

Use ephemeral responses for normal actions:

```text
✅ Pulse updated.
✅ Entry confirmed.
🎉 Claim recorded. The organizer has been notified.
⚠️ This giveaway has ended.
```

Never expose a member’s private eligibility failure to the public channel.

---

## 19. Acceptance criteria

### Guild Pulse

- An administrator can enable and configure Guild Pulse through the management panel.
- Text, voice, reactions, events, and manual XP can be enabled independently.
- Anti-spam cooldowns and caps prevent obvious farming.
- XP is stored in an auditable ledger.
- A member can view a polished progress card privately.
- Level-up announcements are configurable.
- Configured progression rewards can be assigned safely.
- Team Leader roles are never assigned or removed by the progression system.
- A public leaderboard message refreshes every 5 minutes under normal operation.
- The leaderboard is never intentionally older than 10 minutes.
- The leaderboard message is updated in place rather than spammed with new messages.
- A member can see their own rank even outside the top list.
- Seasons preserve historical data.
- The system resumes correctly after a bot restart.

### Giveaway Operations

- An administrator can create a giveaway without commands.
- The system supports immediate and scheduled giveaways.
- The public message clearly states that the organizer supplies the prize.
- Eligibility rules are visible and evaluated at entry and draw time.
- A member cannot create duplicate entries.
- Entries survive bot restarts.
- Giveaways end automatically at the configured time.
- Offline/overdue giveaways recover safely on startup.
- Winners are selected using an auditable, secure, deterministic draw procedure.
- Claim deadlines are enforced.
- Unclaimed winners can be rerolled.
- Rerolls preserve the original draw history.
- Administrators can pause, end early, cancel, or repair giveaways.
- Cancellation never silently deletes entry history.
- The bot never purchases, holds, transfers, verifies, or distributes a prize.
- The bot never collects sensitive payout or delivery information.

### Existing behavior protection

- Team creation, editing, deletion, player management, and private channel permissions continue to work.
- Team Leader role protection remains absolute.
- No slash commands are added.
- All meaningful mutations are audit logged.

---

## 20. Recommended implementation order

1. Add Guild Pulse and giveaway database models plus Alembic migration.
2. Add shared scheduler and idempotency utilities.
3. Implement XP ledger and text participation rules.
4. Implement progress calculations and member progress cards.
5. Implement configurable leaderboard publishing and five-minute refresh.
6. Implement voice, reaction, event, and manual XP sources.
7. Implement progression reward validation and level-up behavior.
8. Implement giveaway configuration, publication, and entry handling.
9. Implement eligibility revalidation, scheduled closing, and secure drawing.
10. Implement claims, expirations, rerolls, cancellation, and history.
11. Add startup recovery and repair states.
12. Add integration tests for duplicate events, concurrent entries, leaderboard freshness, restarts, role hierarchy, and prize-responsibility boundaries.
13. Deploy behind the existing Railway workflow and verify logs before enabling the systems for production guilds.

Prefer small, focused services:

- `pulse_service`
- `xp_ledger_service`
- `leaderboard_service`
- `progression_reward_service`
- `giveaway_service`
- `giveaway_draw_service`
- `scheduler_service`
- `community_system_recovery_service`

All Discord mutations must be explicit, validated, transactional where possible, and logged with enough context to diagnose failures without exposing secrets or private member data.
