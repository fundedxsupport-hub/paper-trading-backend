import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "FundedX Paper Trading API"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "fundedx_paper_trading"
    cors_origins: str = "*"
    pl_refresh_seconds: int = 2
    market_price_url_template: str = ""
    timezone_offset_minutes: int = 330

    @property
    def parsed_cors_origins(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mongo_url=os.getenv("MONGO_URL", "mongodb://localhost:27017"),
        mongo_db_name=os.getenv("MONGO_DB_NAME", "fundedx_paper_trading"),
        cors_origins=os.getenv("CORS_ORIGINS", "*"),
        pl_refresh_seconds=int(os.getenv("PL_REFRESH_SECONDS", "2")),
        market_price_url_template=os.getenv("MARKET_PRICE_URL_TEMPLATE", ""),
        timezone_offset_minutes=int(os.getenv("TIMEZONE_OFFSET_MINUTES", "330")),
    )
