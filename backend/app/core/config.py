from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "event-planner"
    database_url: str = "postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere"
    # Frontend origins allowed to call the API. Override in .env as JSON:
    # CORS_ORIGINS=["http://localhost:5173","https://your-frontend.example.com"]
    cors_origins: list[str] = ["http://localhost:5173"]
    # Supabase Auth (US16a): the project URL, e.g. https://<project-ref>.supabase.co. Access tokens are
    # checked against its public keys.
    supabase_url: str = ""
    # Keep the X-User-Id / X-Attendee-Id identity stubs working alongside tokens. On for local dev,
    # tests and CI E2E; off in production, where only a valid token identifies the caller.
    auth_dev_headers: bool = False
    # The seed's Supabase logins (SCRUM-104). The secret key (sb_secret_…) is for admin calls from the
    # backend only: never commit it, print it or send it to the browser. Without it the seed skips logins.
    supabase_secret_key: str = ""
    # One shared password for every seeded login (demo accounts only).
    seed_auth_password: str = ""


settings = Settings()
