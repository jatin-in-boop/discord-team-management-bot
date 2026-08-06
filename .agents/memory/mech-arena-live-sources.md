---
name: Mech Arena live sources
description: External source layout and freshness constraints for the planned grounded Mech Arena assistant.
---

The public calculator exposes weapons inside `/list.json` and weapon upgrade-cost records inside `/mech_upgrade_costs.json`; it does not expose a separate weapon-cost JSON endpoint among the discovered public assets. The same site exposes pilot and mod list/cost assets.

**Why:** The assistant needs weapon calculations, but assuming a separate weapon JSON would create a false dependency. The site also exposes no discovered webhook or push API, so instant synchronization cannot be promised.

**How to apply:** Treat the calculator as a polled source with allowlisted URLs, conditional requests/content hashes, parser validation, source timestamps, and optional on-demand refresh before calculations. Show freshness to users and refuse unsupported or stale answers rather than implying guaranteed live data.