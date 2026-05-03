from datetime import datetime
from typing import Any

import requests
from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.config import get_settings
from app.database import market_prices, trades, wallets
from app.models import CloseTradeRequest, MarketPriceRequest, MarketPricesRequest, PlaceTradeRequest, WalletSyncRequest
from app.utils import clean_dict, day_bounds_utc, is_market_open, new_uuid, now_utc

settings = get_settings()


def calculate_pl(side: str, entry_price: float, current_price: float, quantity: float) -> float:
    if side == "BUY":
        return round((current_price - entry_price) * quantity, 2)
    return round((entry_price - current_price) * quantity, 2)


def _fetch_external_price(symbol: str) -> float | None:
    if not settings.market_price_url_template:
        return None
    url = settings.market_price_url_template.format(symbol=symbol)
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        body = response.json()
        price = body.get("price") if isinstance(body, dict) else None
        return float(price) if price else None
    except Exception:
        return None


def set_market_price(payload: MarketPriceRequest) -> dict[str, Any]:
    timestamp = now_utc()
    doc = market_prices.find_one_and_update(
        {"symbol": payload.symbol},
        {"$set": {"symbol": payload.symbol, "price": payload.price, "updated_at": timestamp}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    refresh_open_trades(symbol=payload.symbol)
    return clean_dict(doc)


def set_market_prices(payload: MarketPricesRequest) -> dict[str, Any]:
    updated = 0
    for price in payload.prices:
        set_market_price(price)
        updated += 1
    return {"updated": updated}


def get_market_price(symbol: str, fallback: float | None = None) -> float:
    symbol = symbol.strip().upper()
    external = _fetch_external_price(symbol)
    if external is not None:
        set_market_price(MarketPriceRequest(symbol=symbol, price=external))
        return external

    doc = market_prices.find_one({"symbol": symbol})
    if doc and doc.get("price"):
        return float(doc["price"])

    if fallback is not None:
        set_market_price(MarketPriceRequest(symbol=symbol, price=fallback))
        return fallback

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No market price available for {symbol}. Update price first.",
    )


def ensure_wallet(client_id: str) -> dict[str, Any]:
    timestamp = now_utc()
    doc = wallets.find_one_and_update(
        {"client_id": client_id},
        {
            "$setOnInsert": {
                "client_id": client_id,
                "virtual_capital": 0.0,
                "realized_pl": 0.0,
                "unrealized_pl": 0.0,
                "total_pl": 0.0,
                "created_at": timestamp,
            },
            "$set": {"updated_at": timestamp},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return clean_dict(doc)


def sync_wallet(payload: WalletSyncRequest) -> dict[str, Any]:
    timestamp = now_utc()
    doc = wallets.find_one_and_update(
        {"client_id": payload.client_id},
        {
            "$setOnInsert": {
                "client_id": payload.client_id,
                "realized_pl": 0.0,
                "unrealized_pl": 0.0,
                "total_pl": 0.0,
                "created_at": timestamp,
            },
            "$set": {
                "virtual_capital": float(payload.virtual_capital),
                "updated_at": timestamp,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return clean_dict(doc)


def refresh_wallet_unrealized(client_id: str) -> None:
    open_trades = trades.find({"client_id": client_id, "status": "OPEN"})
    unrealized = round(sum(float(trade.get("profit_loss", 0)) for trade in open_trades), 2)
    wallet = ensure_wallet(client_id)
    realized = float(wallet.get("realized_pl", 0))
    wallets.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "unrealized_pl": unrealized,
                "total_pl": round(realized + unrealized, 2),
                "updated_at": now_utc(),
            }
        },
    )


def refresh_open_trades(symbol: str | None = None) -> None:
    query: dict[str, Any] = {"status": "OPEN"}
    if symbol:
        query["symbol"] = symbol.strip().upper()

    affected_clients: set[str] = set()
    for trade in trades.find(query):
        try:
            current_price = get_market_price(trade["symbol"])
        except HTTPException:
            continue
        pl = calculate_pl(trade["side"], float(trade["entry_price"]), current_price, float(trade["quantity"]))
        trades.update_one(
            {"trade_id": trade["trade_id"]},
            {"$set": {"current_price": current_price, "profit_loss": pl, "updated_at": now_utc()}},
        )
        affected_clients.add(trade["client_id"])

    for client_id in affected_clients:
        refresh_wallet_unrealized(client_id)


def place_trade(payload: PlaceTradeRequest) -> dict[str, Any]:
    if not is_market_open(settings.timezone_offset_minutes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Market is closed")

    current_price = get_market_price(payload.symbol, payload.market_price)
    if payload.order_type.value == "LIMIT":
        if payload.limit_price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit price required")
        if payload.side.value == "BUY" and current_price > payload.limit_price:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit price not reached")
        if payload.side.value == "SELL" and current_price < payload.limit_price:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit price not reached")
        entry_price = float(payload.limit_price)
    else:
        entry_price = current_price

    if payload.wallet_balance is not None:
        sync_wallet(WalletSyncRequest(client_id=payload.client_id, virtual_capital=payload.wallet_balance))

    wallet = ensure_wallet(payload.client_id)
    required_amount = round(entry_price * float(payload.quantity), 2)
    available = float(wallet.get("virtual_capital", 0))
    if required_amount > available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds")

    timestamp = now_utc()
    trade = {
        "trade_id": new_uuid(),
        "client_id": payload.client_id,
        "symbol": payload.symbol,
        "side": payload.side.value,
        "quantity": float(payload.quantity),
        "order_type": payload.order_type.value,
        "product": payload.product.value,
        "entry_price": entry_price,
        "current_price": current_price,
        "exit_price": None,
        "required_amount": required_amount,
        "profit_loss": 0.0,
        "status": "OPEN",
        "opened_at": timestamp,
        "updated_at": timestamp,
    }
    wallets.update_one(
        {"client_id": payload.client_id},
        {"$inc": {"virtual_capital": -required_amount}, "$set": {"updated_at": timestamp}},
    )
    trades.insert_one(trade)
    return clean_dict(trade)


def close_trade(payload: CloseTradeRequest) -> dict[str, Any]:
    trade = trades.find_one({"trade_id": payload.trade_id, "client_id": payload.client_id})
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    if trade["status"] != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade already closed")

    exit_price = get_market_price(trade["symbol"], payload.market_price)
    final_pl = calculate_pl(trade["side"], float(trade["entry_price"]), exit_price, float(trade["quantity"]))
    timestamp = now_utc()
    trades.update_one(
        {"trade_id": payload.trade_id},
        {
            "$set": {
                "current_price": exit_price,
                "exit_price": exit_price,
                "profit_loss": final_pl,
                "status": "CLOSED",
                "closed_at": timestamp,
                "updated_at": timestamp,
            }
        },
    )

    ensure_wallet(payload.client_id)
    required_amount = float(trade.get("required_amount", 0))
    wallets.update_one(
        {"client_id": payload.client_id},
        {
            "$inc": {"virtual_capital": required_amount + final_pl, "realized_pl": final_pl},
            "$set": {"updated_at": timestamp},
        },
    )
    refresh_wallet_unrealized(payload.client_id)
    return clean_dict(trades.find_one({"trade_id": payload.trade_id}))


def get_wallet(client_id: str) -> dict[str, Any]:
    refresh_open_trades()
    return clean_dict(ensure_wallet(client_id.strip().upper()))


def get_open_trades(client_id: str) -> list[dict[str, Any]]:
    refresh_open_trades()
    return [
        clean_dict(trade)
        for trade in trades.find({"client_id": client_id.strip().upper(), "status": "OPEN"}).sort("opened_at", -1)
    ]


def get_portfolio(client_id: str, day: datetime | None = None) -> list[dict[str, Any]]:
    refresh_open_trades()
    start, end = day_bounds_utc(day, settings.timezone_offset_minutes)
    query = {
        "client_id": client_id.strip().upper(),
        "opened_at": {"$gte": start, "$lte": end},
    }
    return [clean_dict(trade) for trade in trades.find(query).sort("opened_at", -1)]


def get_trade_history(client_id: str) -> list[dict[str, Any]]:
    refresh_open_trades()
    return [clean_dict(trade) for trade in trades.find({"client_id": client_id.strip().upper()}).sort("opened_at", -1)]
