from typing import Dict, List, Optional
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

    # When True the extractor fills unreadable fields with sample values (old UI-demo behaviour).
    # Default False: unreadable fields are left empty and reported as Missing. The assistant always
    # uses False.
    EXTRACTION_DEMO_FALLBACKS: bool = False

    # Approximate exchange rates (units per 1 USD) used only to add up mixed-currency dashboard
    # totals. The web app's currency switcher uses the same values (frontend/src/utils/currency.ts).
    FX_RATES_PER_USD: Dict[str, float] = {"USD": 1.0, "INR": 83.0, "EUR": 0.92, "GBP": 0.79}

    # Fraud engine amount thresholds, in the invoice's currency.
    FRAUD_REVIEW_THRESHOLD_DEFAULT: float = 25000.0     # USD/EUR/GBP: "substantial value"
    FRAUD_HIGH_THRESHOLD_DEFAULT: float = 100000.0      # USD/EUR/GBP: "high value"
    FRAUD_SPIKE_MIN_DEFAULT: float = 1000.0
    FRAUD_REVIEW_THRESHOLD_INR: float = 200000.0        # ₹2,00,000
    FRAUD_HIGH_THRESHOLD_INR: float = 1000000.0         # ₹10,00,000
    FRAUD_SPIKE_MIN_INR: float = 50000.0

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

    # Demo seed accounts (admin/reviewer/user @invoshield.ai). Never created when APP_ENV=production.
    SEED_DEMO_USERS: bool = True
    # Production bootstrap admin (created once, must change password on first login)
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None
    BOOTSTRAP_ADMIN_ORGANIZATION: str = "General"

    # ---------------- InvoShield Assistant (conversational agent) ----------------
    AGENT_ENABLED: bool = True
    # "anthropic" uses the Claude API with native tool use; "offline" is a deterministic
    # English-only fallback used for demos/tests when no API key is configured.
    # "anthropic" (Claude) or "gemini" (Google). "offline" is a basic English-only fallback.
    AGENT_LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: Optional[str] = None
    AGENT_MODEL: str = "claude-sonnet-5-5"
    # Google Gemini: key from https://aistudio.google.com/app/apikey
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AGENT_MAX_TOKENS: int = 1024
    AGENT_MAX_TOOL_ROUNDS: int = 6
    AGENT_HISTORY_TURNS: int = 12
    # "mock" records outbound messages in the DB/memory only; "live" calls Meta / SMTP for real.
    AGENT_CHANNEL_MODE: str = "mock"
    AGENT_DEFAULT_ORGANIZATION: str = "General"
    AGENT_BUSINESS_NAME: str = "Our Business"
    AGENT_TIMEZONE: str = "Asia/Kolkata"
    AGENT_RATE_LIMIT_PER_MINUTE: int = 20
    AGENT_MAX_MEDIA_MB: int = 10
    AGENT_CONFIRMATION_TTL_MINUTES: int = 15

    # WhatsApp Business Cloud API (Meta)
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_APP_SECRET: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en"

    # Email channel
    EMAIL_WEBHOOK_SECRET: Optional[str] = None
    EMAIL_IMAP_HOST: Optional[str] = None
    EMAIL_IMAP_USER: Optional[str] = None
    EMAIL_IMAP_PASSWORD: Optional[str] = None
    EMAIL_IMAP_FOLDER: str = "INBOX"
    EMAIL_SMTP_HOST: Optional[str] = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USER: Optional[str] = None
    EMAIL_SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM_ADDRESS: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    @property
    def is_production(self) -> bool:
        return (self.APP_ENV or "").lower() in ("production", "prod")


# Known insecure defaults that must never be used in production.
INSECURE_DEFAULTS = {
    "JWT_SECRET_KEY": {
        "dev_secret_key_invoshield_super_secure_jwt_token_2026_production_grade",
        "change_this_to_a_secure_random_64_character_hex_secret_key_in_production",
    },
    "AES_ENCRYPTION_KEY": {"MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="},
    "S3_ACCESS_KEY_ID": {"minioadmin"},
    "S3_SECRET_ACCESS_KEY": {"minioadmin"},
}


def insecure_settings(s: "Settings") -> List[str]:
    """Return the names of settings still using a known insecure default value."""
    return [name for name, bad in INSECURE_DEFAULTS.items() if getattr(s, name, None) in bad]


def enforce_production_safety(s: "Settings") -> None:
    """Refuse to start in production with default secrets or credentials."""
    if not s.is_production:
        return
    bad = insecure_settings(s)
    if bad:
        raise RuntimeError(
            "Refusing to start with APP_ENV=production while these settings use insecure "
            f"defaults: {', '.join(bad)}. Set real values in .env."
        )


settings = Settings()
