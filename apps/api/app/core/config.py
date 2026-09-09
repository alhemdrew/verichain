import os
from functools import lru_cache

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    app_name: str = "VeriChain"
    env: str = "development"
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    database_url: str = "postgresql+psycopg2://verichain:verichain_pass@localhost:5432/verichain_dev"
    frontend_url: str = "http://localhost:5173"
    verichain_auto_sign: bool = False

    @validator("secret_key")
    def secret_key_required(cls, value: str) -> str:
        if not value:
            raise ValueError("SECRET_KEY must be configured in the environment")
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
