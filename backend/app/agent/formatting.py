"""Small formatting helpers shared by tools and the offline provider."""
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.config import settings

from app.utils.money import CURRENCY_SYMBOLS, format_money, indian_grouping

__all__ = ["CURRENCY_SYMBOLS", "format_money", "indian_grouping", "agent_tz", "local_today",
           "local_day_bounds_utc", "parse_iso_date", "fmt_dt"]


def agent_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.AGENT_TIMEZONE)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def local_today() -> date:
    return datetime.now(agent_tz()).date()


def local_day_bounds_utc(day: date) -> Tuple[datetime, datetime]:
    """Naive-UTC [start, end) for a local calendar day (DB stores naive UTC timestamps)."""
    tz = agent_tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def fmt_dt(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(agent_tz()).strftime("%d %b %Y, %I:%M %p")
