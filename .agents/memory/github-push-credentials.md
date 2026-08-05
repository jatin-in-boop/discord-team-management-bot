---
name: GitHub push credentials
description: Workspace-specific limitation encountered when pushing the repository to GitHub.
---

GitHub pushes through both the shell remote and the authenticated Git helper require connected GitHub source-control credentials. A workspace secret or unrelated GitHub token may be present without satisfying that source-control credential requirement.

**Why:** The implementation was committed successfully, but both push paths rejected the remote because no GitHub source-control credentials were connected.

**How to apply:** Keep completed work committed locally, avoid exposing tokens or rewriting remotes with credentials, and have the user connect GitHub source control before retrying the push.