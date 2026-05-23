from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def format_slot_time(value: datetime) -> str:
    return value.astimezone(IST).strftime("%d %b, %I:%M %p")
