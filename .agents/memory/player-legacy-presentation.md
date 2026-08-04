---
name: PLAYER LEGACY presentation migration
description: The requested role presentation migration preserves existing Pulse progression and managed-role identity while changing only presentation.
---

The PLAYER LEGACY migration treats existing milestone role IDs, permissions, hierarchy, colors, level ranges, reward records, and member assignments as immutable. Manual Squad Power and Tournament Bracket roles are informational display roles only: they are created by exact name, positioned below milestone roles, and excluded from Pulse-managed records and automation.

**Why:** The presentation rename must not alter progression behavior or overwrite live Discord role state.

**How to apply:** Future presentation changes should update names and UI copy only; do not add manual display roles to Pulse rewards, managed-role registries, XP sources, self-role systems, or permission logic.