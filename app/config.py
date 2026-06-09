from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Email Mailing Service"
    database_url: str = "sqlite:///./data/email_service.db"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "./data/uploads"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@example.com"
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_timeout: float = 5.0

    watchdog_interval_seconds: int = 1
    watchdog_stale_seconds: int = 5
    events_stream_maxlen: int = 10000
    import_batch_size: int = 1000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
