# Team Management Bot — Architecture Documentation

## Project Structure

```
/
├── bot/
│   ├── client.py                 # Main Discord bot class
│   ├── embeds/
│   │   └── base.py               # Reusable embed builders
│   ├── services/
│   │   ├── guild_setup.py
│   │   ├── panel_restoration.py
│   │   ├── panel_update.py
│   │   ├── permission_service.py
│   │   └── audit_service.py
│   └── views/
│       └── management_panel.py   # Persistent management panel
├── config/
│   └── settings.py               # Pydantic configuration
├── database/
│   ├── engine.py
│   └── session.py
├── models/
│   └── models.py                 # SQLAlchemy models
├── app_logging/
│   └── logger.py
├── utilities/
│   └── exceptions.py
├── docs/
│   └── ARCHITECTURE.md
├── main.py
└── requirements.txt
```

## Startup Lifecycle

1. Configuration loaded via Pydantic
2. Structured logging initialized
3. Alembic applies the database schema
4. Persistent views registered
5. Guild configurations loaded
6. Management panels restored
7. Health validation performed

## Persistent View Lifecycle

- All views use `timeout=None` + stable `custom_id`
- Registered in `setup_hook()`
- Automatically re-attached on restart via `PanelRestorationService`

## Permission Model

- Centralized in `PermissionService`
- Only administrators may interact with management UI
- Ephemeral error responses for unauthorized users

## Database

- Single source of truth: Supabase PostgreSQL
- All Discord resources tracked with foreign keys and constraints
- Automatic rollback on transaction failure

## Logging

- Structured logging with `structlog`
- All major events (startup, setup, recovery, errors) are logged

This architecture ensures Phase 2+ can focus exclusively on feature implementation.
