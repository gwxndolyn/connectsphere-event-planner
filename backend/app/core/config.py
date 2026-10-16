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


settings = Settings()
