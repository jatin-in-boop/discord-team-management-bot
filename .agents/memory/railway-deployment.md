---
name: Railway deployment access
description: External Railway provisioning constraint for this project.
---

The Railway API accepts the configured token. Broad project listing may return no projects, but the linked production project/service/environment IDs from the Railway UI are accessible directly. Variable reads and writes work through the backboard GraphQL endpoint; writes may intermittently hit an edge 403 and should be retried with pacing.

**Why:** Deploying without a known project target would risk creating or modifying paid infrastructure without an explicit workspace/project choice; once the user supplies the exact Railway URL, direct scoped operations are safe.

**How to apply:** Use exact project, service, and environment IDs from the user’s Railway URL. Never record secret values here. Use `variableUpsert` with `skipDeploys` when staging multiple variables, then call `serviceInstanceRedeploy`. Discord.py object APIs should be checked against the installed version; for AFK voice channels, use `guild.afk_channel` and compare its ID rather than relying on an `afk_channel_id` attribute.