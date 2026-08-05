---
name: Community banner defaults
description: Current welcome and goodbye banner delivery and reset behavior.
---

Welcome and goodbye defaults are shipped as local attachments so they work in
both plain messages and embeds. A versioned per-guild marker clears old custom
banner URLs once when a new default asset set is introduced and can also apply
one-time presentation migrations.

**Why:** Discord embeds cannot reliably display a local file unless the message
also uploads it, and the user requested existing custom banners be reset once.

**How to apply:** Change the reset or layout version whenever intentionally
replacing the default assets or presentation, and keep sends using the same
attachment helper.

The minimal embed contract is title, user-authored message, and banner only;
automatic identity, status, timestamps, footers, and boilerplate copy are not
part of the rendered community message.