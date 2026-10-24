import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "InvoShield AI"
    APP_ENV: str = "development"
    PORT: int = 8000
    DEBUG: bool = True

    # Database: if postgres is down or not configured, session manager will handle fallback
    DATABASE_URL: str = "sqlite:///./invoshield.db"

    # Security
    JWT_SECRET_KEY: str = "dev_secret_key_invoshield_super_secure_jwt_token_2026_production_grade"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # AES-256 Key (base64-encoded 32-byte key)
    # Default 32 bytes: b"0123456789abcdef0123456789abcdef" -> "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    AES_ENCRYPTION_KEY: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

    # Cloud Storage (MinIO / S3)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "invoshield-invoices"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    LOCAL_STORAGE_DIR: str = "./storage_data"

    # OCR Settings
    TESSERACT_CMD: Optional[str] = None
    OCR_LANGUAGE: str = "eng"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:80",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "*"
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
