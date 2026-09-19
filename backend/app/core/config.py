from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "event-planner"
    database_url: str = "postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere"
    # Frontend origins allowed to call the API. Override in .env as JSON:
    # CORS_ORIGINS=["http://localhost:5173","https://your-frontend.example.com"]
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
