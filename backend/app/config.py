"""Configuration management for the backend."""
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from YAML and environment variables."""

    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    CONFIG_DIR: Path = BASE_DIR / "config" / "backend"

    # App settings
    APP_NAME: str = "APP Automated Testing Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, validation_alias="DEBUG")
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DB_HOST: str = Field(default="localhost", validation_alias="DB_HOST")
    DB_PORT: int = Field(default=3306, validation_alias="DB_PORT")
    DB_USER: str = Field(default="root", validation_alias="DB_USER")
    DB_PASSWORD: str = Field(default="", validation_alias="DB_PASSWORD")
    DB_NAME: str = Field(default="auto_test", validation_alias="DB_NAME")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_HOST: str = Field(default="localhost", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")

    # MinIO
    MINIO_ENDPOINT: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", validation_alias="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", validation_alias="MINIO_SECRET_KEY")
    MINIO_BUCKET: str = Field(default="auto-test", validation_alias="MINIO_BUCKET")
    MINIO_SECURE: bool = False

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # JWT
    JWT_SECRET_KEY: str = Field(default="your-secret-key-change-in-production", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Config (loaded from llm.yaml)
    llm_config: dict = {}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def load_llm_config(self) -> None:
        """Load LLM configuration from YAML file."""
        llm_config_path = self.CONFIG_DIR / "llm.yaml"
        if llm_config_path.exists():
            with open(llm_config_path, "r", encoding="utf-8") as f:
                self.llm_config = yaml.safe_load(f) or {}

    def get_database_url(self) -> str:
        """Get async database URL."""
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    def get_sync_database_url(self) -> str:
        """Get sync database URL for migrations."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Global settings instance
settings = Settings()
settings.load_llm_config()
