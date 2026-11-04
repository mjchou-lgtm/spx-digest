"""NYSE session calendar and post-slot windows (Pacific time)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal

from digest import config


@dataclass(frozen=True)
class Session:
    date: date
    open_et: datetime
    close_et: datetime
    early_close: bool


@lru_cache(maxsize=1)
def _nyse():
    return mcal.get_calendar("NYSE")


@lru_cache(maxsize=64)
def _schedule(year: int):
    return _nyse().schedule(start_date=f"{year - 1}-12-01", end_date=f"{year + 1}-01-31")


def session(d: date) -> Session | None:
    sch = _schedule(d.year)
    key = d.isoformat()
    if key not in sch.index.strftime("%Y-%m-%d"):
        return None
    row = sch.loc[sch.index.strftime("%Y-%m-%d") == key].iloc[0]
    o = row["market_open"].tz_convert(config.ET).to_pydatetime()
    c = row["market_close"].tz_convert(config.ET).to_pydatetime()
    return Session(date=d, open_et=o, close_et=c, early_close=c.time() < time(16, 0))


def is_trading_day(d: date) -> bool:
    return session(d) is not None


def prev_trading_day(d: date) -> date:
    x = d - timedelta(days=1)
    while not is_trading_day(x):
        x -= timedelta(days=1)
    return x


def next_trading_day(d: date) -> date:
    x = d + timedelta(days=1)
    while not is_trading_day(x):
        x += timedelta(days=1)
    return x


def scheduled_time_pt(post_type: str, d: date) -> datetime:
    """Slot time in PT. On early-close days the afternoon post moves to close - 60 min."""
    hh, mm = config.POST_TIMES_PT[post_type]
    slot = datetime.combine(d, time(hh, mm), tzinfo=config.PT)
    s = session(d)
    if post_type == "afternoon" and s and s.early_close:
        slot = s.close_et.astimezone(config.PT) - timedelta(minutes=config.EARLY_CLOSE_AFTERNOON_LEAD_MIN)
    return slot


def posts_on(post_type: str, d: date) -> bool:
    """Which posts run on a session. Early-close days have no midsession post."""
    s = session(d)
    return s is not None and not (post_type == "midsession" and s.early_close)


def check_window(post_type: str, now: datetime) -> tuple[bool, str]:
    """Is `now` inside this post's run window today? Returns (ok, one-line reason)."""
    now_pt = now.astimezone(config.PT)
    d = now_pt.date()
    s = session(d)
    if s is None:
        return False, f"skip {post_type}: {d} is not an NYSE trading day"
    if not posts_on(post_type, d):
        return False, f"skip {post_type}: {d} is an early-close day (no midsession post)"
    slot = scheduled_time_pt(post_type, d)
    delta_min = (now_pt - slot).total_seconds() / 60
    if delta_min < -config.WINDOW_EARLY_TOLERANCE_MIN:
        return False, f"skip {post_type}: {now_pt:%H:%M} PT is {-delta_min:.0f} min before the {slot:%H:%M} PT slot"
    if delta_min > config.WINDOW_LATE_TOLERANCE_MIN:
        return False, f"skip {post_type}: {now_pt:%H:%M} PT is {delta_min:.0f} min after the {slot:%H:%M} PT slot (limit {config.WINDOW_LATE_TOLERANCE_MIN})"
    return True, f"run {post_type}: slot {slot:%H:%M} PT, now {now_pt:%H:%M} PT" + (" (early close)" if s.early_close else "")
