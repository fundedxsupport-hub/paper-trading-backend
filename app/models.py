from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TradeSide(str, Enum):
    buy = "BUY"
    sell = "SELL"


class TradeStatus(str, Enum):
    open = "OPEN"
    closed = "CLOSED"


class PlaceTradeRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    symbol: str = Field(..., min_length=1, max_length=64)
    quantity: float = Field(..., gt=0)
    side: TradeSide
    market_price: float | None = Field(default=None, gt=0)

    @field_validator("client_id", "symbol")
    @classmethod
    def strip_upper(cls, value: str) -> str:
        return value.strip().upper()


class CloseTradeRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    trade_id: str = Field(..., min_length=1, max_length=128)
    market_price: float | None = Field(default=None, gt=0)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, value: str) -> str:
        return value.strip().upper()


class MarketPriceRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=64)
    price: float = Field(..., gt=0)

    @field_validator("symbol")
    @classmethod
    def strip_symbol(cls, value: str) -> str:
        return value.strip().upper()


class MarketPricesRequest(BaseModel):
    prices: list[MarketPriceRequest] = Field(..., min_length=1)


class WalletResponse(BaseModel):
    client_id: str
    virtual_capital: float
    realized_pl: float
    unrealized_pl: float
    total_pl: float
    updated_at: datetime | str | None = None


class TradeResponse(BaseModel):
    trade_id: str
    client_id: str
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    current_price: float
    exit_price: float | None = None
    profit_loss: float
    status: TradeStatus
    opened_at: datetime | str
    closed_at: datetime | str | None = None
