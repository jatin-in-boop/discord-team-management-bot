---
name: Community event delivery
description: Durable rules for invite tracking and server audit-log delivery.
---

Invite tracking and server logs are administrator-mapped features: the bot must
never create a destination channel automatically.

Server audit activity should be coalesced into short summaries instead of
sending one Discord message per event. Message edits/deletions, voice activity,
and bot automation are opt-in detail categories; ordinary moderation, member,
channel, role, invite, and server events use the default set.

**Why:** High-volume Discord events can overwhelm a log channel and make useful
moderation history difficult to read.

**How to apply:** Preserve the existing private management-panel configuration
path and keep new event sources behind explicit settings or category filters.