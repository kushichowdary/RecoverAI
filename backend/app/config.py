import os
from pydantic_settings import BaseSettings

from pydantic import ConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./recoverai.db"
    FRONTEND_ORIGIN: str = ""  # Configurable CORS origin (comma-separated if multiple)
    AI_PROVIDER: str = "mock"  # "mock" or "anthropic"
    ANTHROPIC_API_KEY: str = ""
    RAZORPAY_MODE: str = "mock"  # "mock" or "test"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    
    # Policy defaults
    MAX_RETRY_ATTEMPTS: int = 3
    MAX_AUTOMATIC_RECOVERY_AMOUNT: float = 50000.0  # INR
    MIN_AI_CONFIDENCE: float = 0.70
    DAILY_ACTION_LIMIT: int = 100
    
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
