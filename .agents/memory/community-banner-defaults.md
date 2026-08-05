---
name: Community banner defaults
description: Current welcome and goodbye banner delivery and reset behavior.
---

Welcome and goodbye defaults are shipped as local attachments so they work in
both plain messages and embeds. A versioned per-guild marker clears old custom
banner URLs once when a new default asset set is introduced.

**Why:** Discord embeds cannot reliably display a local file unless the message
also uploads it, and the user requested existing custom banners be reset once.

**How to apply:** Change the reset version whenever intentionally replacing the
default assets, and keep plain/embed sends using the same attachment helper.