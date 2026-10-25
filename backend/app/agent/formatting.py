"""Small formatting helpers shared by tools and the offline provider."""
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.config import settings

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def indian_grouping(n: int) -> str:
    """1234567 -> '12,34,567' (Indian lakh/crore grouping)."""
    s = str(abs(int(n)))
    if len(s) <= 3:
        out = s
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        out = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + out


def format_money(amount: Optional[float], currency: Optional[str] = "INR") -> str:
    amount = float(amount or 0.0)
    cur = (currency or "INR").upper()
    symbol = CURRENCY_SYMBOLS.get(cur, cur + " ")
    whole = int(round(amount * 100)) // 100
    paise = int(round(abs(amount) * 100)) % 100
    if cur == "INR":
        body = indian_grouping(whole)
    else:
        body = f"{whole:,}"
    return f"{symbol}{body}" + (f".{paise:02d}" if paise else "")


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
