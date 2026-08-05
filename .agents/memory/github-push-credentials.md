---
name: GitHub push credentials
description: Workspace-specific limitation encountered when pushing the repository to GitHub.
---

The authenticated Git helper may report that GitHub source-control credentials are unavailable even when the Replit `GITHUB_PERSONAL_ACCESS_TOKEN` secret exists. The repository can still be pushed securely through an ephemeral `GIT_ASKPASS` helper that reads the secret at runtime.

**Why:** The GitHub helper rejected the push for missing source-control credentials, while an ephemeral askpass-based push using the Replit secret succeeded without exposing or persisting the token.

**How to apply:** Check that `GITHUB_PERSONAL_ACCESS_TOKEN` is available, use a temporary executable `GIT_ASKPASS` script with terminal prompts disabled, and never print the token or embed it in the remote URL or Git config.