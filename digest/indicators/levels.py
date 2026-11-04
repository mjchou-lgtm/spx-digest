"""Price levels: prior day, overnight ES range (in SPX points), gap, opens, ATR/ADR."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from digest import config
from digest.indicators import Market, pct


def true_range_atr(daily: pd.DataFrame, n: int = 20):
    if len(daily) < n + 1:
        return None
    h, l, c = daily["h"].to_numpy(float), daily["l"].to_numpy(float), daily["c"].to_numpy(float)
    prev_c = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(abs(h - prev_c), abs(l - prev_c)))[1:]
    return float(np.mean(tr[-n:]))


def average_daily_range(daily: pd.DataFrame, n: int = 10):
    if len(daily) < n:
        return None
    return float((daily["h"] - daily["l"]).iloc[-n:].mean())


def es_spx_basis(m: Market, prior: date):
    """ES minus SPX at the prior cash close (16:00 ET), from 5m bars; daily closes as fallback."""
    spx_c = m.prior_close(config.SPX)
    es = m.intra.get("ES=F")
    if es is not None and len(es) and spx_c is not None:
        close_ts = datetime.combine(prior, time(16, 0), tzinfo=config.ET)
        w = es[(es.index <= close_ts) & (es.index > close_ts - timedelta(minutes=15))]
        if len(w):
            return float(w["c"].iloc[-1]) - spx_c
    es_c = m.prior_close("ES=F")
    if es_c is not None and spx_c is not None:
        return es_c - spx_c  # TODO: ES daily close is the 17:00 ET settle, not 16:00 — small timing mismatch
    return None


def overnight_range(m: Market, prior: date, session_open: datetime, basis):
    """ES high/low between the prior cash close and today's open (or as_of), converted to SPX points."""
    es = m.intra.get("ES=F")
    if es is None or not len(es) or basis is None:
        return None, None
    start = datetime.combine(prior, time(16, 0), tzinfo=config.ET)
    end = min(session_open, m.as_of)
    w = es[(es.index > start) & (es.index < end)]
    if not len(w):
        return None, None
    return float(w["h"].max()) - basis, float(w["l"].min()) - basis


def period_open(m: Market, kind: str, today_open):
    """Open of the first session of this week/month (today's open if today is the first)."""
    hist = m.hist(config.SPX)
    t = m.target
    if kind == "week":
        start = t - timedelta(days=t.weekday())
    else:
        start = t.replace(day=1)
    in_period = hist[[d >= start for d in hist.index]]
    if len(in_period):
        return float(in_period["o"].iloc[0])
    return today_open


def spx_session_bars(m: Market, session_open: datetime, session_close: datetime) -> pd.DataFrame:
    df = m.intra.get(config.SPX)
    if df is None or not len(df):
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    return df[(df.index >= session_open) & (df.index < session_close)]


def compute_levels(m: Market, prior: date, session_open: datetime, session_close: datetime, expected_move_pts):
    out: dict = {}
    hist = m.hist(config.SPX)
    if len(hist):
        last = hist.iloc[-1]
        out.update(prior_date=str(hist.index[-1]), prior_open=last["o"], prior_high=last["h"], prior_low=last["l"], prior_close=last["c"])
    out["atr20_pts"] = true_range_atr(hist, 20)
    out["adr10_pts"] = average_daily_range(hist, 10)

    basis = es_spx_basis(m, prior)
    out["es_spx_basis_pts"] = basis
    on_hi, on_lo = overnight_range(m, prior, session_open, basis)
    out["overnight_high"], out["overnight_low"] = on_hi, on_lo
    out["overnight_range_pts"] = (on_hi - on_lo) if on_hi is not None else None

    sess = spx_session_bars(m, session_open, session_close)
    prior_close = out.get("prior_close")
    if len(sess):
        out["session_open"] = float(sess["o"].iloc[0])
        out["session_high"] = float(sess["h"].max())
        out["session_low"] = float(sess["l"].min())
        out["spot"] = float(sess["c"].iloc[-1])
        out["range_used_pts"] = out["session_high"] - out["session_low"]
        if out["atr20_pts"]:
            out["range_used_atr_pct"] = out["range_used_pts"] / out["atr20_pts"] * 100
        out["spot_source"] = "SPX 5m"
        gap_ref = out["session_open"]
    else:
        es_last = m.latest("ES=F")
        if es_last is not None and basis is not None:
            out["spot"] = es_last - basis
            out["spot_source"] = "ES-implied (ES last - prior-close basis)"
        gap_ref = out.get("spot")
    if gap_ref is not None and prior_close is not None:
        out["gap_pts"] = gap_ref - prior_close
        out["gap_pct"] = pct(gap_ref, prior_close)
        if expected_move_pts:
            out["gap_em_fraction"] = out["gap_pts"] / expected_move_pts
    out["weekly_open"] = period_open(m, "week", out.get("session_open"))
    out["monthly_open"] = period_open(m, "month", out.get("session_open"))
    return out
