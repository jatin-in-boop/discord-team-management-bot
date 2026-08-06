---
name: Groq request headers
description: Provider-edge behavior required for Groq chat requests from this bot.
---

Groq chat requests from this bot must include an explicit normal `User-Agent` and `Accept: application/json` header. Python urllib’s default request fingerprint can be rejected by the provider edge with HTTP 403 / Cloudflare code 1010 even when the same key and model succeed with curl.

**Why:** Production logged Groq 403 responses, while direct tests showed the configured keys and model were valid; adding explicit headers made the same Python request succeed.

**How to apply:** Preserve these headers in any future Groq client refactor. Treat 403 as a temporary per-key cooldown and fail over without exposing provider internals to members.