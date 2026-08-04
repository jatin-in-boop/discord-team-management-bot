---
name: Persistent Pulse interactions
description: Discord component lifecycle constraint for live Guild Pulse leaderboard messages.
---

Live Guild Pulse leaderboard buttons must use stable guild-specific custom IDs, a non-expiring view, and startup registration. Existing configured leaderboard messages should be force-refreshed after a restart so stale component state is replaced.

**Why:** Discord buttons on an old live message stop working after a process restart or view timeout unless the bot re-registers matching persistent components.

**How to apply:** Preserve this lifecycle whenever changing Pulse leaderboard buttons or adding other persistent controls to the live leaderboard message.