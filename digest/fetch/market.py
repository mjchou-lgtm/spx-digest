"""yfinance fetchers: daily bars, 5-min bars, SPX option chain, earnings dates."""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from digest import config
from digest.fetch.base import FetchResult, fetch_with_retry

log = logging.getLogger("digest.fetch.market")

YF_TIMEOUT_S = 30


def _clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if math.isnan(f) or math.isinf(f) else f


def _frame_to_bars(df: pd.DataFrame) -> list[dict]:
    out = []
    for ts, row in df.iterrows():
        if pd.isna(row.get("Close")):
            continue
        t = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        out.append(
            {
                "t": t,
                "o": _clean(row.get("Open")),
                "h": _clean(row.get("High")),
                "l": _clean(row.get("Low")),
                "c": _clean(row.get("Close")),
                "v": _clean(row.get("Volume")),
            }
        )
    return out


def _download(tickers: list[str], **kw) -> dict[str, list[dict]]:
    df = yf.download(
        tickers,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
        timeout=YF_TIMEOUT_S,
        **kw,
    )
    if df is None or df.empty:
        raise RuntimeError("yfinance returned no data")
    out: dict[str, list[dict]] = {}
    for t in tickers:
        if t in df.columns.get_level_values(0):
            bars = _frame_to_bars(df[t])
            if bars:
                out[t] = bars
    if not out:
        raise RuntimeError("yfinance returned no usable bars")
    return out


def fetch_daily(target: date) -> FetchResult:
    start = target - timedelta(days=140)
    end = target + timedelta(days=1)
    res = fetch_with_retry(
        "yfinance:daily",
        lambda: _download(config.DAILY_TICKERS, start=start.isoformat(), end=end.isoformat(), interval="1d"),
    )
    if res.ok:
        missing = [t for t in config.DAILY_TICKERS if t not in res.data]
        res.meta["missing_tickers"] = missing
    return res


def fetch_intraday(target: date) -> FetchResult:
    # Start a few days back so the prior evening's futures session is included.
    start = target - timedelta(days=4)
    end = target + timedelta(days=1)
    res = fetch_with_retry(
        "yfinance:5m",
        lambda: _download(
            config.INTRADAY_TICKERS, start=start.isoformat(), end=end.isoformat(), interval="5m", prepost=True
        ),
    )
    if res.ok:
        res.meta["missing_tickers"] = [t for t in config.INTRADAY_TICKERS if t not in res.data]
    return res


CHAIN_COLS = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]


def _chain_side(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        rows.append({c: _clean(r.get(c)) for c in CHAIN_COLS})
    return rows


def _next_weekly(expiries: list[str], target: date) -> str | None:
    """First Friday expiry strictly after the target date."""
    for e in expiries:
        d = date.fromisoformat(e)
        if d > target and d.weekday() == 4:
            return e
    return None


def _fetch_chain(symbol: str, target: date) -> dict:
    t = yf.Ticker(symbol)
    expiries = list(t.options or [])
    if not expiries:
        raise RuntimeError(f"no expiries listed for {symbol}")
    zero = target.isoformat()
    if zero not in expiries:
        raise RuntimeError(f"{symbol} has no {zero} expiry (listed: {expiries[:4]})")
    weekly = _next_weekly(expiries, target)
    out = {"symbol": symbol, "expiries_listed": expiries[:12], "chains": {}}
    for exp in [zero, weekly]:
        if not exp:
            continue
        ch = t.option_chain(exp)
        calls, puts = _chain_side(ch.calls), _chain_side(ch.puts)
        if not calls or not puts:
            raise RuntimeError(f"{symbol} {exp} chain empty")
        out["chains"][exp] = {"calls": calls, "puts": puts}
    out["expiry_0dte"] = zero
    out["expiry_weekly"] = weekly
    try:
        out["underlying_price"] = _clean(t.fast_info.get("lastPrice"))
    except Exception:  # noqa: BLE001
        out["underlying_price"] = None
    return out


def fetch_option_chain(target: date) -> FetchResult:
    """^SPX chain for the target date's expiry; falls back to SPY (strikes x10 downstream)."""
    if target != datetime.now(config.PT).date():
        return FetchResult(
            source="yfinance:option_chain",
            fetched_at=datetime.now(config.UTC).isoformat(timespec="seconds"),
            ok=False,
            error="historical option chains are not available from yfinance",
        )
    primary = fetch_with_retry(f"yfinance:chain:{config.CHAIN_PRIMARY}", lambda: _fetch_chain(config.CHAIN_PRIMARY, target))
    if primary.ok:
        primary.meta["fallback"] = False
        return primary
    fb = fetch_with_retry(f"yfinance:chain:{config.CHAIN_FALLBACK}", lambda: _fetch_chain(config.CHAIN_FALLBACK, target))
    fb.meta["fallback"] = True
    fb.meta["primary_error"] = primary.error
    return fb


def _earnings_for(sym: str) -> dict:
    cal = yf.Ticker(sym).calendar or {}
    dates = cal.get("Earnings Date") or []
    if not isinstance(dates, (list, tuple)):
        dates = [dates]
    return {"symbol": sym, "earnings_dates": [str(d) for d in dates if d is not None]}


def fetch_earnings(symbols: list[str]) -> FetchResult:
    def run():
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda s: fetch_with_retry(f"yfinance:calendar:{s}", lambda: _earnings_for(s), retries=2), symbols))
        data = [r.data for r in results if r.ok]
        failed = [s for s, r in zip(symbols, results) if not r.ok]
        if not data:
            raise RuntimeError("no earnings calendars fetched")
        return {"items": data, "failed": failed}

    return fetch_with_retry("yfinance:earnings", run, retries=1)
