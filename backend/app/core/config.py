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
    ai_api_base_url: str = os.getenv("AI_API_BASE_URL", "")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_model: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    ai_temperature: float = float(os.getenv("AI_TEMPERATURE", "0.7"))
    ai_enable_mock: bool = os.getenv("AI_ENABLE_MOCK", "true").lower() == "true"
    ai_vote_window_seconds: float = float(os.getenv("AI_VOTE_WINDOW_SECONDS", "5"))
    ai_speak_window_seconds: int = int(os.getenv("AI_SPEAK_WINDOW_SECONDS", "8"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "cors_origins", _split_csv(os.getenv("CORS_ORIGINS", "http://localhost:5173")))


settings = Settings()
