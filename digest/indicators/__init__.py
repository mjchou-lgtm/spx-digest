"""Deterministic indicators. Pure functions over bars/chains; no I/O."""
from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd

from digest import config


def r2(x, nd: int = 2):
    """Round for the brief (Claude quotes numbers exactly as given)."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, nd)


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def bars_df(bars: list[dict] | None) -> pd.DataFrame:
    """Bars (from raw json) -> DataFrame indexed by tz-aware ET timestamps."""
    if not bars:
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    df = pd.DataFrame(bars)
    idx = pd.to_datetime(df.pop("t"), utc=True)
    df.index = idx.dt.tz_convert(config.ET) if hasattr(idx, "dt") else idx.tz_convert(config.ET)
    return df.sort_index()


def daily_df(bars: list[dict] | None) -> pd.DataFrame:
    """Daily bars indexed by naive date."""
    if not bars:
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    df = pd.DataFrame(bars)
    df.index = pd.to_datetime(df.pop("t").str[:10]).dt.date
    return df.sort_index()


def history_before(df: pd.DataFrame, target: date) -> pd.DataFrame:
    return df[[d < target for d in df.index]]


class Market:
    """Read-side view over one run's raw bars, trimmed to `as_of`."""

    def __init__(self, daily: dict | None, intraday: dict | None, target: date, as_of: datetime):
        self.target = target
        self.as_of = as_of.astimezone(config.ET)
        self.daily = {k: daily_df(v) for k, v in (daily or {}).items()}
        self.intra = {}
        for k, v in (intraday or {}).items():
            df = bars_df(v)
            self.intra[k] = df[df.index <= self.as_of]

    def hist(self, t: str) -> pd.DataFrame:
        return history_before(self.daily.get(t, pd.DataFrame()), self.target)

    def prior_close(self, t: str):
        h = self.hist(t)
        return float(h["c"].iloc[-1]) if len(h) else None

    def latest(self, t: str, session_open: datetime | None = None):
        """Most recent price as of `as_of`: today's 5m bars, else today's daily
        row once the session has opened, else None (not yet trading today)."""
        df = self.intra.get(t)
        if df is not None and len(df):
            today = df[[ts.date() == self.target for ts in df.index]]
            if len(today):
                return float(today["c"].iloc[-1])
        d = self.daily.get(t)
        if d is not None and len(d) and self.target in d.index:
            if session_open is None or self.as_of >= session_open:
                # TODO: for historical replays this is the day's final close, not the as-of value.
                return float(d.loc[self.target, "c"])
        return None

    def change_pct(self, t: str, session_open: datetime | None = None):
        return pct(self.latest(t, session_open), self.prior_close(t))

    def last_intraday_ts(self) -> datetime | None:
        ts = [df.index[-1] for df in self.intra.values() if len(df)]
        return max(ts) if ts else None


def annualized_rv_pct(closes: pd.Series | np.ndarray, n: int, periods_per_year: float = 252.0):
    c = np.asarray(closes, dtype=float)
    c = c[~np.isnan(c)]
    if len(c) < n + 1:
        return None
    r = np.diff(np.log(c[-(n + 1):]))
    return float(np.std(r, ddof=1) * math.sqrt(periods_per_year) * 100.0)
