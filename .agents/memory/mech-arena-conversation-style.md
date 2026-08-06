---
name: Mech Arena conversation style
description: The intended balance between natural member-facing chat and strict factual grounding.
---

Member-facing Mech Arena replies should sound like a normal helpful chatbot, including for name-only prompts such as “Panther” or “Revoker.” Internal words like evidence, verification, snapshots, and conflict should stay out of ordinary answers.

**Why:** Members found repeated refusal and provenance language unnatural even though the assistant’s factual safeguards were useful.

**How to apply:** Keep source retrieval, deterministic calculations, numeric claim checks, and targeted disagreement detection internal. Combine compatible records; mention uncertainty conversationally only when the requested detail is missing or specifically disagrees.