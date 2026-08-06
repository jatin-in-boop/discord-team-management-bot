# Mech Arena database assistant

The assistant answers Discord questions from two independent, read-only sources:

1. The configured Google Spreadsheet is the organized game database.
2. `https://mecharena.infohubhq.in/` supplies calculator data, including the
   shared mech/weapon list and upgrade-cost records, plus pilot and mod costs.

The sources are stored as immutable snapshots. A snapshot is published only
after validation; malformed or missing data is not allowed to replace the last
approved snapshot. Calculator data is unofficial community data and answers
show its snapshot time where relevant.

## Freshness and live updates

The bot polls sources on the configured interval (`MECH_ARENA_POLL_SECONDS`,
default 15 minutes). A member calculation also refreshes the calculator first
when the guild setting allows it. The website exposes no webhook, so instant
updates cannot be promised. Approved snapshots older than
`MECH_ARENA_MAX_STALE_SECONDS` (default 24 hours) are refused. The bot reports
the snapshot time and refuses unsupported calculations instead of pretending
stale data is current.

## Answer safety

Grok receives only records selected by the application. It is instructed not
to create facts, and generated numeric claims are rejected when their numeric
tokens are absent from the evidence. Upgrade totals are calculated in Python,
not by the model. Missing levels, entities, or cost rows return a clear
unavailable response. The member-facing answer is conversational: internal
terms such as evidence, verification, snapshots, and conflicts are not shown
unless a specific requested field genuinely has incompatible values.

The six Groq keys are read only from Replit Secrets. Keys are rotated on a
round-robin basis and temporarily cooled down after rate limits or transient
failures. Secret values are never logged or persisted.

## Discord use

An administrator opens **Community Systems → Mech Arena AI**, refreshes sources,
views freshness, and enables member questions. Members mention the bot with any
Mech Arena question in a channel where the feature is enabled, such as asking
what a mech or weapon does, sending only a name like `Panther` or `Revoker`,
comparing records, or requesting an upgrade cost.
Responses are sent as ordinary Discord text messages, not embeds. Answers use
fresh matching evidence when available; an unrelated stale source does not
block a response, while a record found only in stale data is refused until that
source is refreshed. Compatible records are combined, and unsupported
questions and calculations are not guessed.