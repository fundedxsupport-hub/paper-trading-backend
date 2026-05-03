import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import check_connection, setup_indexes
from app.models import CloseTradeRequest, MarketPriceRequest, MarketPricesRequest, PlaceTradeRequest, WalletSyncRequest
from app.services import (
    close_trade,
    get_open_trades,
    get_portfolio,
    get_trade_history,
    get_wallet,
    place_trade,
    refresh_open_trades,
    set_market_price,
    set_market_prices,
    sync_wallet,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_indexes()
    refresh_task = asyncio.create_task(_refresh_open_pl_loop())
    yield
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass


async def _refresh_open_pl_loop() -> None:
    while True:
        try:
            refresh_open_trades()
        except Exception as exc:
            print(f"Paper P/L refresh skipped: {exc}")
        await asyncio.sleep(max(settings.pl_refresh_seconds, 1))


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Paper trading backend for challenge account trades, wallet, P/L and history.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health() -> dict:
    return {"message": settings.app_name, "mongo": check_connection()}


@app.post("/market-price")
def market_price(payload: MarketPriceRequest) -> dict:
    return set_market_price(payload)


@app.post("/market-prices")
def market_prices(payload: MarketPricesRequest) -> dict:
    return set_market_prices(payload)


@app.post("/refresh-pl")
def refresh_pl() -> dict:
    refresh_open_trades()
    return {"message": "Open trade P/L refreshed"}


@app.post("/place-trade")
def api_place_trade(payload: PlaceTradeRequest) -> dict:
    return place_trade(payload)


@app.post("/wallet-sync")
def api_wallet_sync(payload: WalletSyncRequest) -> dict:
    return sync_wallet(payload)


@app.post("/close-trade")
def api_close_trade(payload: CloseTradeRequest) -> dict:
    return close_trade(payload)


@app.get("/wallet/{client_id}")
def api_wallet(client_id: str) -> dict:
    return get_wallet(client_id)


@app.get("/trades/open/{client_id}")
def api_open_trades(client_id: str) -> list[dict]:
    return get_open_trades(client_id)


@app.get("/portfolio/{client_id}")
def api_portfolio(client_id: str) -> list[dict]:
    return get_portfolio(client_id)


@app.get("/trades/history/{client_id}")
def api_trade_history(client_id: str) -> list[dict]:
    return get_trade_history(client_id)
