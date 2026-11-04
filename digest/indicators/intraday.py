"""Intraday structure: opening range, VWAP, realised vol so far, high/low retests."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from digest import config
from digest.indicators import Market

OR_MINUTES = 30
BARS_PER_DAY_5M = 78


def opening_range(sess: pd.DataFrame, session_open: datetime, as_of: datetime):
    end = session_open + timedelta(minutes=OR_MINUTES)
    w = sess[sess.index < end]
    if not len(w):
        return None, None, False
    return float(w["h"].max()), float(w["l"].min()), as_of >= end


def spot_vs_range(spot, hi, lo):
    if spot is None or hi is None or lo is None:
        return None
    if spot > hi:
        return "above"
    if spot < lo:
        return "below"
    return "inside"


def vwap_with_proxy_volume(spx: pd.DataFrame, vol_proxy: pd.DataFrame | None):
    """SPX has no volume; weight SPX typical price by SPY 5m volume at the same timestamps."""
    if not len(spx):
        return None, None
    tp = (spx["h"] + spx["l"] + spx["c"]) / 3.0
    if vol_proxy is not None and len(vol_proxy):
        v = vol_proxy["v"].reindex(spx.index).fillna(0.0)
        if v.sum() > 0:
            return float((tp * v).sum() / v.sum()), "SPX typical price weighted by SPY 5m volume"
    return float(tp.mean()), "SPX typical price, equal-weighted (no volume proxy)"


def rv_today_pct(sess: pd.DataFrame):
    c = sess["c"].to_numpy(float)
    if len(c) < 4:
        return None
    r = np.diff(np.log(c))
    return float(np.std(r, ddof=1) * math.sqrt(BARS_PER_DAY_5M * 252) * 100)


def retested(sess: pd.DataFrame, side: str, tol_pts: float, min_gap_bars: int = 3) -> bool | None:
    """True if price returned within tol of the session extreme after first reaching it
    and pulling back by at least 2x tol, with >= min_gap_bars in between."""
    if len(sess) < min_gap_bars + 2:
        return None
    if side == "high":
        ext = sess["h"].max()
        near = (sess["h"] >= ext - tol_pts).to_numpy()
        away = (sess["c"] < ext - 2 * tol_pts).to_numpy()
    else:
        ext = sess["l"].min()
        near = (sess["l"] <= ext + tol_pts).to_numpy()
        away = (sess["c"] > ext + 2 * tol_pts).to_numpy()
    idx = np.flatnonzero(near)
    first = idx[0]
    for j in idx[1:]:
        if j - first >= min_gap_bars and away[first + 1 : j].any():
            return True
    return False


def compute_intraday(m: Market, sess: pd.DataFrame, session_open: datetime, spot, atr_pts, em_pts, retest_tol_atr_frac: float) -> dict:
    out: dict = {}
    if not len(sess):
        return out
    out["minutes_since_open"] = int((m.as_of - session_open).total_seconds() // 60)
    hi, lo, complete = opening_range(sess, session_open, m.as_of)
    out.update(or_high=hi, or_low=lo, or_complete=complete)
    out["spot_vs_or"] = spot_vs_range(spot, hi, lo) if complete else None
    spy = m.intra.get("SPY")
    spy_sess = spy[spy.index >= session_open] if spy is not None else None
    out["vwap"], out["vwap_method"] = vwap_with_proxy_volume(sess, spy_sess)
    if spot is not None and out["vwap"] is not None:
        out["spot_minus_vwap_pts"] = spot - out["vwap"]
    out["rv_today_pct"] = rv_today_pct(sess)
    if em_pts:
        out["realized_range_em_fraction"] = float(sess["h"].max() - sess["l"].min()) / em_pts
    tol = (atr_pts or 0) * retest_tol_atr_frac or 2.0
    out["high_retested"] = retested(sess, "high", tol)
    out["low_retested"] = retested(sess, "low", tol)
    return out
