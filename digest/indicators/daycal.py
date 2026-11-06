"""What is special about a session's date: day of the week, options expiries, month and quarter end.

Pure calendar arithmetic over the NYSE session calendar. SPX has an option expiring every
session, so "daily" is the baseline; the other kinds mean more contracts than usual expire.
Nothing here measures positioning (open interest or dealer gamma are not used).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
QUARTER_MONTHS = (3, 6, 9, 12)


def third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def _on_or_before(d: date, is_trading_day: Callable[[date], bool]) -> date:
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def monthly_opex(year: int, month: int, is_trading_day: Callable[[date], bool]) -> date:
    """Standard monthly options expiration: the third Friday, or the session before it on a holiday."""
    return _on_or_before(third_friday(year, month), is_trading_day)


def vix_expiry(year: int, month: int, is_trading_day: Callable[[date], bool]) -> date:
    """VIX futures and options settlement for a month: 30 days before the third Friday of the
    following month (a Wednesday), or the session before it on a holiday."""
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return _on_or_before(third_friday(ny, nm) - timedelta(days=30), is_trading_day)


def _last_session_of_week(d: date, is_trading_day: Callable[[date], bool]) -> date:
    return _on_or_before(d + timedelta(days=4 - d.weekday()), is_trading_day)


def _last_session_of_month(year: int, month: int, is_trading_day: Callable[[date], bool]) -> date:
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return _on_or_before(date(ny, nm, 1) - timedelta(days=1), is_trading_day)


def day_context(d: date, is_trading_day: Callable[[date], bool]) -> dict:
    """Calendar facts for a trading day `d` (Monday to Friday)."""
    opex = monthly_opex(d.year, d.month, is_trading_day)
    if opex < d:
        ny, nm = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        opex = monthly_opex(ny, nm, is_trading_day)
    if d == opex:
        kind = "quarterly" if d.month in QUARTER_MONTHS else "monthly"
    elif d == _last_session_of_week(d, is_trading_day):
        kind = "weekly"
    else:
        kind = "daily"
    month_end = d == _last_session_of_month(d.year, d.month, is_trading_day)
    return {
        "weekday": WEEKDAYS[d.weekday()],
        "expiry_kind": kind,
        "monthly_opex_date": opex.isoformat(),
        "days_to_monthly_opex": (opex - d).days,
        "opex_week": opex - timedelta(days=opex.weekday()) <= d <= opex,
        "vix_expiry_today": d == vix_expiry(d.year, d.month, is_trading_day),
        "month_end": month_end,
        "quarter_end": month_end and d.month in QUARTER_MONTHS,
    }
