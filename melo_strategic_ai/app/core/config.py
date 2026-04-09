from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Caminho do .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    # ========================
    # Configuração base
    # ========================
    APP_NAME: str = "Melo Strategic AI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    # ========================
    # Segurança
    # ========================
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ========================
    # Banco de dados
    # ========================
    DATABASE_URL: str

    # ========================
    # Stripe
    # ========================
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID: str

    # ========================
    # URLs
    # ========================
    FRONTEND_URL: str = "http://localhost:5500"
    BACKEND_URL: str = "http://127.0.0.1:8000"

    # ========================
    # Pydantic config
    # ========================
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()