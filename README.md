# Discord Team Management Bot

Production-ready Discord bot for automating tournament team creation and
management inside Discord servers. Administrators manage everything through
buttons, modals, and searchable user-select menus.

## What it does

- Creates a team with its team role, Team Leader role, category, four channels,
  and permissions.
- Adds and removes players through Discord's native user selector.
- Renames teams and updates their SP range while keeping Discord resources in
  sync.
- Deletes teams with confirmation and resilient cleanup.
- Restores the management panel after a restart.
- Records important actions in the audit log.

The bot creates the **Team Leader** role but never assigns, removes, transfers,
or otherwise manages that role. Server administrators always handle assignment
manually.

## Deploy to Railway

This repository is configured as a long-running Railway worker using the
included `Dockerfile` and `railway.toml`.

1. Create a Railway project and add a PostgreSQL database.
2. Deploy this repository as a service using the repository root.
3. Add the required variables below to the bot service.
4. Invite the bot to your Discord server with the permissions it needs and
   enable the **Server Members Intent** and **Message Content Intent** in the
   Discord Developer Portal.
5. Deploy. The container runs `alembic upgrade head` before starting the bot.

Required Railway variables:

```text
DISCORD_TOKEN=...
DATABASE_URL=postgresql://...
```

Optional variables:

```text
DISCORD_CLIENT_ID=...
ENVIRONMENT=production
LOG_LEVEL=INFO
BOT_VERSION=1.0.0
SCHEMA_VERSION=1
```

`SUPABASE_DB_URL` is also supported for existing Supabase deployments and takes
precedence over `DATABASE_URL` when both are present. `SUPABASE_URL` and
`SUPABASE_KEY` remain supported for compatibility but are not required by the
current bot runtime.

## Local development

```bash
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

Never commit `.env` or any Discord, database, GitHub, or Railway credential.

## Project structure

```text
bot/                 Discord client, views, modals, embeds, and services
app_logging/         JSON structured logging for Railway
config/              Pydantic environment settings
database/            Async SQLAlchemy engine and transactions
models/              SQLAlchemy models
migrations/          Alembic environment and revisions
utilities/            Domain exceptions
```

## Development rules

- Use `get_db_session()` for transactions.
- Use SQLAlchemy ORM rather than raw application queries.
- Route important actions through `AuditService.log_action()`.
- Preserve the Team Leader role policy above.
- Do not introduce slash commands when the persistent management panel can
  support the workflow.
