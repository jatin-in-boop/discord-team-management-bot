---
name: Alembic revision discipline
description: Deployment-safe migration graph constraints for this bot.
---

Alembic migration IDs must be globally unique. New migrations must continue the
current chain rather than reusing a revision number already used by another
feature branch.

**Why:** Railway runs `alembic upgrade head` before starting the worker, and
duplicate IDs or multiple heads prevent the bot from starting at all.

**How to apply:** Before pushing schema changes, inspect every file in
`migrations/versions`, verify the parent chain, and confirm exactly one head.