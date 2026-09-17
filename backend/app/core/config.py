from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "event-planner"
    database_url: str = "postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere"


settings = Settings()
