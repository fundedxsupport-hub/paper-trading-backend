from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import get_settings

settings = get_settings()
client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
db: Database = client[settings.mongo_db_name]

trades = db["paper_trades"]
wallets = db["paper_wallets"]
market_prices = db["market_prices"]


def setup_indexes() -> None:
    indexes = (
        (trades, [("trade_id", ASCENDING)], {"unique": True}),
        (trades, [("client_id", ASCENDING), ("status", ASCENDING), ("opened_at", DESCENDING)], {}),
        (trades, [("client_id", ASCENDING), ("opened_at", DESCENDING)], {}),
        (wallets, [("client_id", ASCENDING)], {"unique": True}),
        (market_prices, [("symbol", ASCENDING)], {"unique": True}),
    )
    try:
        for collection, keys, options in indexes:
            collection.create_index(keys, **options)
    except PyMongoError as exc:
        print(f"MongoDB index setup skipped: {exc}")


def check_connection() -> bool:
    try:
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False
