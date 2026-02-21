"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Platform configuration loaded from environment variables."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    k8s_namespace: str = "devops-ai"
    aws_region: str = "eu-north-1"
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379"
    prometheus_port: int = 9090

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
