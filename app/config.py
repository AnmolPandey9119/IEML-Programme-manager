import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    SECRET_KEY: str = "dev-only-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    INVITE_EXPIRE_DAYS: int = 7
    # Public address of this app. Used in invitation emails and in the website embed snippet.
    FRONTEND_URL: str = "http://localhost:8000"
    # Event days are calendar dates; "within 48 hours of the event day" is measured in this zone.
    EVENT_TIMEZONE: str = "Asia/Kolkata"
    MAX_PHOTO_MB: int = 5
    # Internal tool: if set (comma separated, e.g. "iemltd.com,ieml.in"), only these email domains can create the first admin,
    # be invited, or open an account. Empty = no domain restriction.
    ALLOWED_EMAIL_DOMAINS: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""


settings = Settings()

if settings.SECRET_KEY == "dev-only-secret":
    logging.getLogger("config").warning(
        "SECRET_KEY is the development default. Set a long random value in .env before deploying."
    )