from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # Discord
    discord_token: str = Field(..., alias="DISCORD_TOKEN")
    discord_client_id: str | None = Field(default=None, alias="DISCORD_CLIENT_ID")

    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Supabase
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_key: str | None = Field(default=None, alias="SUPABASE_KEY")
    supabase_db_url: str | None = Field(default=None, alias="SUPABASE_DB_URL")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Mech Arena grounded assistant
    google_sheet_id: str | None = Field(default=None, alias="GOOGLE_SHEET_ID")
    google_service_account_json: str | None = Field(
        default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON"
    )
    groq_api_key_1: str | None = Field(default=None, alias="GROQ_API_KEY_1")
    groq_api_key_2: str | None = Field(default=None, alias="GROQ_API_KEY_2")
    groq_api_key_3: str | None = Field(default=None, alias="GROQ_API_KEY_3")
    groq_api_key_4: str | None = Field(default=None, alias="GROQ_API_KEY_4")
    groq_api_key_5: str | None = Field(default=None, alias="GROQ_API_KEY_5")
    groq_api_key_6: str | None = Field(default=None, alias="GROQ_API_KEY_6")
    mech_arena_poll_seconds: int = Field(default=900, alias="MECH_ARENA_POLL_SECONDS")
    mech_arena_max_stale_seconds: int = Field(default=86400, alias="MECH_ARENA_MAX_STALE_SECONDS")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # Bot metadata
    bot_version: str = Field(default="1.0.0", alias="BOT_VERSION")
    schema_version: int = Field(default=1, alias="SCHEMA_VERSION")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def groq_api_keys(self) -> list[str]:
        return [
            key for key in (
                self.groq_api_key_1,
                self.groq_api_key_2,
                self.groq_api_key_3,
                self.groq_api_key_4,
                self.groq_api_key_5,
                self.groq_api_key_6,
            ) if key
        ]

    @property
    def db_url(self) -> str:
        """Return the configured async PostgreSQL URL.

        Supabase deployments use SUPABASE_DB_URL. Railway PostgreSQL services
        commonly expose DATABASE_URL, so accepting both keeps deployment
        configuration portable without changing the application code.
        """
        value = self.supabase_db_url or self.database_url
        if not value:
            raise ValueError("SUPABASE_DB_URL or DATABASE_URL must be configured")
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        # PostgreSQL providers commonly expose libpq's `sslmode` query option.
        # asyncpg expects the equivalent option as `ssl`; leaving `sslmode` in
        # the URL causes SQLAlchemy startup/migrations to fail before connecting.
        parsed = urlsplit(value)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        sslmode = query.pop("sslmode", None)
        if sslmode and "ssl" not in query:
            query["ssl"] = sslmode
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
        )


def get_settings() -> Settings:
    return Settings()  # type: ignore
