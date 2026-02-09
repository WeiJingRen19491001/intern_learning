import os
from typing import List, Union, Any
from dotenv import load_dotenv
from pydantic import AnyHttpUrl, PostgresDsn, validator
from pydantic_settings import BaseSettings

# Automatically find and load .env file
# This looks for .env in current directory and parent directories
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "LUMI Customer Service Agent"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    # BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    BACKEND_CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            # Handle JSON string representation of list like '["http://localhost:8000"]'
            if isinstance(v, str) and v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return []
            return v
        raise ValueError(v)

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "lumi_db"
    POSTGRES_PORT: int = 5432
    
    SQLALCHEMY_DATABASE_URI: Union[str, None] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Union[str, None], values: dict) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=int(values.get("POSTGRES_PORT")),
            path=f"{values.get('POSTGRES_DB') or ''}",
        ).unicode_string()

    # Bailian / Dashscope
    DASHSCOPE_API_KEY: str = ""
    BAILIAN_APP_ID: str = ""

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
