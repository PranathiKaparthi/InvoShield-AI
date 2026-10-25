"""Currency formatting shared by services and the assistant (Indian grouping for INR)."""
from typing import Optional

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
