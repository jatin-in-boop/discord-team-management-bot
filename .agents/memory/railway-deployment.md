---
name: Railway deployment access
description: External Railway provisioning constraint for this project.
---

The Railway API accepts the configured token, but broad project listing currently returns no accessible projects even though the GitHub deployment integration can expose the linked project/service IDs. Deployment diagnostics may need to use the deployment metadata or linked service IDs.

**Why:** Deploying without a known project target would risk creating or modifying paid infrastructure without an explicit workspace/project choice.

**How to apply:** Use the linked Railway project/service IDs from deployment metadata when available. Never record secret values here. Discord.py object APIs should be checked against the installed version; for AFK voice channels, use `guild.afk_channel` and compare its ID rather than relying on an `afk_channel_id` attribute.