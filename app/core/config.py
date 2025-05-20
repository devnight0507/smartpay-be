"""
Application configuration.
"""

from typing import Any, Optional

from pydantic import PostgresDsn, RedisDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Core Settings
    PROJECT_NAME: str = "SmartPay Backend"
    PROJECT_DESCRIPTION: str = "FastAPI Microservice Template"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str

    # API Settings
    API_PREFIX: str = "/api"
    CORS_ORIGINS_STR: str = "*"

    # Database Settings
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        data = info.data
        if not data:
            raise ValueError("Missing data for DATABASE_URI")

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=data.get("POSTGRES_USER"),
            password=data.get("POSTGRES_PASSWORD"),
            host=data.get("POSTGRES_SERVER"),
            port=int(data.get("POSTGRES_PORT", 5432)),
            path=f"{data.get('POSTGRES_DB') or ''}",
        )

    # Cache Settings
    REDIS_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URI: Optional[RedisDsn] = None

    @field_validator("REDIS_URI", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        data = info.data
        if not data:
            raise ValueError("Missing data for REDIS_URI")

        # Skip if Redis is not enabled
        if not data.get("REDIS_ENABLED", True):
            return None

        if isinstance(v, str):
            return v

        return RedisDsn.build(
            scheme="redis",
            host=data.get("REDIS_HOST", "localhost"),
            port=int(data.get("REDIS_PORT", 6379)),
            path=f"/{data.get('REDIS_DB', 0)}",
            password=data.get("REDIS_PASSWORD"),
        )

    # Kafka Settings
    KAFKA_ENABLED: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "smartpay-be"
    KAFKA_AUTO_CREATE_TOPICS: bool = True
    KAFKA_DEFAULT_TOPIC_PARTITIONS: int = 1
    KAFKA_DEFAULT_TOPIC_REPLICATION: int = 1
    KAFKA_TOPIC_ITEMS_EVENTS: str = "items.events"

    @field_validator("KAFKA_ENABLED", mode="before")
    @classmethod
    def parse_kafka_enabled(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() != "false"
        return bool(v)

    # Sentry Settings
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Prometheus Metrics
    ENABLE_METRICS: bool = True

    # Logging Settings
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True

    # Tracing Settings
    ENABLE_TRACING: bool = True
    OTLP_ENDPOINT: Optional[str] = None


# Provide required parameters as environment variables or hardcode for development
settings = Settings(
    SECRET_KEY="development_secret_key",
    POSTGRES_SERVER="localhost",
    POSTGRES_USER="postgres",
    POSTGRES_PASSWORD="postgres",
    POSTGRES_DB="fastapi",
)
