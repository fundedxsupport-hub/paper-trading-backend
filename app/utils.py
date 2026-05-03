from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4

from bson import ObjectId


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return uuid4().hex


def day_bounds_utc(day: datetime | None = None, offset_minutes: int = 330) -> tuple[datetime, datetime]:
    offset = timezone(timedelta(minutes=offset_minutes))
    base = (day or now_utc()).astimezone(offset)
    local_start = datetime.combine(base.date(), time.min, tzinfo=offset)
    local_end = datetime.combine(base.date(), time.max, tzinfo=offset)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def is_market_open(offset_minutes: int = 330) -> bool:
    offset = timezone(timedelta(minutes=offset_minutes))
    local_now = now_utc().astimezone(offset)
    if local_now.weekday() >= 5:
        return False
    market_open = time(9, 15)
    market_close = time(15, 30)
    return market_open <= local_now.time() <= market_close


def clean_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_value(item) for key, item in value.items()}
    return value


def clean_dict(value: dict[str, Any] | None) -> dict[str, Any]:
    return clean_value(value or {})
