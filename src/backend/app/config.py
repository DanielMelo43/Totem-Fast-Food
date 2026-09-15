import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://smashgo:change-this-db-password@localhost:5432/smashgo")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "change-this-password")
    cpf_encryption_key: str = os.getenv("CPF_ENCRYPTION_KEY", "development-only-cpf-key-change-in-production")
    allowed_origins: tuple[str, ...] = tuple(
        value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if value.strip()
    )


settings = Settings()
