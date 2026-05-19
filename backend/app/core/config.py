from dataclasses import dataclass
import os


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "WolfBot Backend")
    app_env: str = os.getenv("APP_ENV", "development")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    cors_origins: list[str] = None  # type: ignore[assignment]
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "cors_origins", _split_csv(os.getenv("CORS_ORIGINS", "http://localhost:5173")))


settings = Settings()
