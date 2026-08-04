---
name: Guild Pulse cap semantics
description: Durable behavior for configurable Guild Pulse XP source limits.
---

Guild Pulse source daily caps apply independently per member and per XP source. An award that would cross a positive cap is trimmed to the remaining amount; zero disables that cap.

**Why:** Administrators need predictable limits when changing message, voice, reaction, or event XP values without accidentally allowing one final award to exceed the configured daily total.

**How to apply:** Preserve this behavior in future XP-source editors, service changes, and administrator documentation.