from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    auth_enabled: bool = False
    api_key: str = ""

    # Two-key model (TEAM_INTEGRATION_PLAN.md D9), used only by endpoints
    # that need to tell a human coordinator apart from n8n/AI automation —
    # everything else still uses the single api_key above unchanged.
    coordinator_api_key: str = ""
    automation_api_key: str = ""

    cors_origins: str = "*"
    app_env: str = "local"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
