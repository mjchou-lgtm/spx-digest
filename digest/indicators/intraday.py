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


def running_vwap(spx: pd.DataFrame, vol_proxy: pd.DataFrame | None) -> pd.Series:
    """Cumulative session VWAP at each bar (same weighting as vwap_with_proxy_volume)."""
    tp = (spx["h"] + spx["l"] + spx["c"]) / 3.0
    v = vol_proxy["v"].reindex(spx.index).fillna(0.0) if vol_proxy is not None and len(vol_proxy) else None
    if v is None or v.sum() <= 0:
        return tp.expanding().mean()
    cum_v = v.cumsum()
    return ((tp * v).cumsum() / cum_v.where(cum_v > 0)).fillna(tp.expanding().mean())


def vwap_crosses(sess: pd.DataFrame, vwap: pd.Series, min_pts: float = 0.0):
    """(crosses, fraction of closes above VWAP). A cross is a 5-min close moving from one side
    of the running VWAP to the other; closes within min_pts of VWAP do not change the side."""
    d = (sess["c"] - vwap).to_numpy(float)
    side, crosses, above, n = 0, 0, 0, 0
    for x in d:
        if np.isnan(x):
            continue
        n += 1
        above += x > 0
        s = 1 if x > min_pts else -1 if x < -min_pts else 0
        if s and side and s != side:
            crosses += 1
        side = s or side
    return crosses, (above / n if n else None)


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


def _at(session_open: datetime, hhmm: str) -> datetime:
    h, mi = map(int, hhmm.split(":"))
    return session_open.replace(hour=h, minute=mi, second=0, microsecond=0)


def compute_structure(m: Market, sess: pd.DataFrame, session_open: datetime, prior_vah, prior_val, p: dict) -> dict:
    """Inputs for the day-type rules: the 10:30 ET snapshot, VWAP crosses by 11:00 ET,
    the developing profile, acceptance outside developing value, and recent volume."""
    from digest.indicators.profile import profile_shape, session_profile, side_of

    out: dict = {}
    if not len(sess):
        return out
    spy = m.intra.get("SPY")
    spy_sess = spy[spy.index >= session_open] if spy is not None else None
    vw = running_vwap(sess, spy_sess)
    out["vwap_crosses"], _ = vwap_crosses(sess, vw, p.get("vwap_cross_min_pts", 0.0))
    cutoff = _at(session_open, p["vwap_cutoff_et"])
    pre = sess[sess.index < cutoff]
    n, frac = vwap_crosses(pre, vw.reindex(pre.index), p.get("vwap_cross_min_pts", 0.0))
    out.update(vwap_crosses_by_cutoff=n, vwap_above_frac=frac, vwap_cutoff_et=p["vwap_cutoff_et"],
               vwap_check_final=m.as_of >= cutoff, vwap_crossed_both_ways=n >= 2)
    snap_t = _at(session_open, p["classify_time_et"])
    if m.as_of >= snap_t:
        snap = sess[sess.index < snap_t]
        if len(snap):
            s = float(snap["c"].iloc[-1])
            hi, lo, _ = opening_range(sess, session_open, m.as_of)
            out.update(snapshot_time_et=p["classify_time_et"], snapshot_spot=s, snapshot_vs_or=spot_vs_range(s, hi, lo),
                       snapshot_vs_prior_va=side_of(s, prior_vah, prior_val))
    # The balance rule reads the profile as of the cutoff, so the label is fixed once the cutoff has passed.
    cut_prof, _ = session_profile(pre if len(pre) else sess, spy_sess)
    if cut_prof:
        out.update(cutoff_poc=cut_prof["poc"], cutoff_poc_position=cut_prof["poc_position"])
    prof, _ = session_profile(sess, spy_sess)
    if prof:
        out.update(dev_poc=prof["poc"], dev_vah=prof["vah"], dev_val=prof["val"], dev_poc_position=prof["poc_position"],
                   profile_shape=profile_shape(prof, p["profile_upper"], p["profile_lower"], p["elongated_va_frac"]))
        last = sess["c"].iloc[-int(p["acceptance_closes"]):]
        if len(last) >= p["acceptance_closes"]:
            out["accepted_outside_dev_va"] = ("above" if (last > prof["vah"]).all() else "below" if (last < prof["val"]).all() else "no")
    if spy_sess is not None and len(spy_sess):
        lunch = spy_sess[(spy_sess.index >= _at(session_open, "12:00")) & (spy_sess.index < _at(session_open, "13:30"))]["v"]
        recent = spy_sess["v"].iloc[-4:-1]  # skip the bar still forming
        if len(lunch) >= 6 and len(recent) and lunch.mean() > 0 and m.as_of >= _at(session_open, "13:30"):
            out["volume_ratio_recent"] = float(recent.mean() / lunch.mean())
    return out


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
