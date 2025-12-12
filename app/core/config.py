from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Database
    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_URL: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # hCaptcha
    HCAPTCHA_SITE_KEY: str = ""
    HCAPTCHA_SECRET_KEY: str = ""

    # Rate Limiting
    RATE_LIMIT_SIGNUPS_PER_HOUR: int = 5
    RATE_LIMIT_SIGNUPS_PER_DAY: int = 10

    # CORS
    CORS_ORIGINS: str = '["http://localhost:5173"]'

    # Mailcow
    MAILCOW_API_URL: str = ""
    MAILCOW_API_KEY: str = ""

    # Encryption key for sensitive data (recovery email/phone)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # SMTP settings for sending OTP emails
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Afrimail"
    SMTP_USE_TLS: bool = True

    # App
    DEBUG: bool = False
    APP_NAME: str = "Afrimail API"
    APP_VERSION: str = "1.0.0"

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except json.JSONDecodeError:
            return ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
