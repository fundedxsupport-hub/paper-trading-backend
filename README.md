# FundedX Paper Trading Backend

FastAPI backend for paper trading. It does not place real market orders.

## Features

- `POST /place-trade` saves an OPEN BUY/SELL trade.
- `POST /close-trade` closes a trade and updates wallet.
- `POST /market-price` updates live price used by backend calculation.
- `POST /market-prices` bulk-updates live prices from app option-chain feed.
- `GET /portfolio/{client_id}` returns today's trades for Portfolio.
- `GET /trades/open/{client_id}` returns open trades.
- `GET /trades/history/{client_id}` returns full trade history.
- `GET /wallet/{client_id}` returns virtual capital and P/L.

## Run

```powershell
cd C:\Users\HP\paper-trading-backend
copy .env.example .env
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

The Flutter app currently points to `http://192.168.1.13:8002`. If your Wi-Fi IP changes, run `ipconfig`, copy the new IPv4 address, and either update `PaperTradingService.baseUrl` or run Flutter with:

```powershell
flutter run --dart-define=PAPER_TRADING_API_BASE_URL=http://YOUR_IPV4:8002
```

## Example

Update market price:

```json
POST /market-price
{
  "symbol": "NIFTY",
  "price": 22500
}
```

Place trade:

```json
POST /place-trade
{
  "client_id": "FXI123456",
  "symbol": "NIFTY",
  "side": "BUY",
  "quantity": 1
}
```

Close trade:

```json
POST /close-trade
{
  "client_id": "FXI123456",
  "trade_id": "TRADE_ID"
}
```
