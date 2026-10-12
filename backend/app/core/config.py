from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ==========================================
    # 1. Application Configuration
    # ==========================================
    APP_NAME: str = "ERP AI Copilot"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change-this-to-a-secure-random-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # ==========================================
    # 2. Database Configuration (PostgreSQL + pgvector)
    # ==========================================
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "erp_copilot"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_SYNC: Optional[str] = None

    @computed_field
    @property
    def async_database_url(self) -> str:
        """Tự động sinh Async URL (asyncpg) nếu không cung cấp trực tiếp"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Tự động sinh Sync URL (psycopg2) cho Alembic migrations"""
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ==========================================
    # 3. LLM Configuration (Google Gemini & OpenAI)
    # ==========================================
    # Default LLM: Gemini 3.5 Flash-Lite (High speed, cost effective, agentic optimized)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TEMPERATURE: float = 0.2
    GEMINI_MAX_OUTPUT_TOKENS: int = 8192

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ==========================================
    # 4. RAG & Multimodal Embedding Configuration
    # ==========================================
    # Default Embedding: Gemini Embedding 2 (Natively multimodal, Matryoshka support)
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    # Dimension 1536 aligns with PostgreSQL Vector(1536) and pgvector index efficiency
    # (gemini-embedding-2 supports MRL output_dimensionality from 128 to 3072)
    EMBEDDING_DIMENSION: int = 1536

    # ==========================================
    # 5. File & Object Storage Configuration
    # ==========================================
    STORAGE_TYPE: Literal["local", "s3"] = "s3"
    STORAGE_LOCAL_DIR: Path = Path("./data/uploads")
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY: Optional[str] = "minioadmin"
    S3_SECRET_KEY: Optional[str] = "minioadmin"
    S3_BUCKET_NAME: str = "erp-documents"
    S3_REGION: str = "us-east-1"

    # ==========================================
    # 6. Observability & Tracing (Langfuse)
    # ==========================================
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter với cache để hỗ trợ FastAPI Dependency Injection và Testing"""
    return Settings()


settings = get_settings()
