---
name: Replit Python runtime limitation
description: Why local workflow startup cannot validate this Python bot in the current workspace.
---

The current Replit shell uses an externally managed immutable Python environment with no installed project packages. Package installation through the available language-package flow is rejected by PEP 668, so console workflows fail at the first existing dependency import rather than at application code.

**Why:** The bot’s deployment path is Docker-based; `Dockerfile` installs `requirements.txt` before running migrations and `main.py`. Local workflow failure must not be mistaken for a code import regression.

**How to apply:** Use compile-only checks and dependency-free tests locally, and validate runtime startup through the Docker/Railway deployment environment once available. Never bypass the package firewall with ad-hoc system mutation.