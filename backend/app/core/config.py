from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", validation_alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="nlptrader", validation_alias="POSTGRES_DB")
    db_echo: bool = False

    # External APIs
    FINNHUB_API_KEY: str = Field(default="", validation_alias="FINNHUB_API_KEY")
    LLM_API_KEY: str = Field(default="", validation_alias="LLM_API_KEY")
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = Field(default="", validation_alias="GEMINI_API_KEY")

    # Tickers
    TICKERS_STR: str = Field(default="BTC,ETH,XAUUSD,NVDA", validation_alias="TICKERS")

    @property
    def TICKERS(self) -> List[str]:
        return [t.strip().upper() for t in self.TICKERS_STR.split(",") if t.strip()]

    # Ingestion
    LOOKBACK_HOURS: int = 24
    LOOKBACK_DAYS: int = 3
    BATCH_LIMIT: int = 100

    # Price data timeframes
    PRICE_TIMEFRAMES: list = ["15m", "1h", "4h", "1d"]

    # Signal generation
    PREDICTION_HORIZON_HOURS: int = 24
    SENTIMENT_HALF_LIFE_HOURS: float = 48.0
    MIN_ARTICLES_FOR_SENTIMENT: int = 3

    # Ensemble weights
    TA_WEIGHT: float = 0.4
    SENTIMENT_WEIGHT: float = 0.3
    FUNDAMENTAL_WEIGHT: float = 0.3

    # Conflict penalty
    CONFLICT_PENALTY: float = 0.5

    # Embedding / RAG
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_TOP_K: int = 10
    RAG_LOOKBACK_DAYS: int = 7

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
