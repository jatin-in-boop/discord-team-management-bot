---
name: Uploaded asset hygiene
description: Prevent workspace-uploaded reference files from entering application repositories or deployments.
---

Workspace-uploaded reference images can be added to Git by an automatic Replit commit after the agent has prepared a clean code change.

**Why:** A visual reference was unintentionally included in a GitHub push and Railway deployment during a leaderboard polish cycle.

**How to apply:** Before pushing, inspect the commit range and remote tree for uploaded assets. Keep reference files untracked or remove them in a separate cleanup commit before deployment.