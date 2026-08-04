---
name: Railway deployment access
description: External Railway provisioning constraint for this project.
---

The Railway API accepts the configured token, but project listing currently returns no accessible projects. Deployment cannot proceed until a Railway project/service target is created or the token is granted access to one.

**Why:** Deploying without a known project target would risk creating or modifying paid infrastructure without an explicit workspace/project choice.

**How to apply:** Before retrying Railway deployment, select or create the target Railway project, attach PostgreSQL, and configure the bot service with `DISCORD_TOKEN` and `DATABASE_URL`. Never record their values here.