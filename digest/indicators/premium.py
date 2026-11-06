"""Premium / IV block: VIX1D percentile, theta reference (sqrt-of-time), IV crush vs the 09:35 ET print."""
from __future__ import annotations

import math
from datetime import datetime

from digest.indicators import Market


def vix1d_stats(m: Market, current, p: dict) -> dict:
    """Percentile rank of VIX1D against its last 20 closes, and the label."""
    h = m.hist("^VIX1D")
    if current is None or len(h) < 20:
        return {}
    last = h["c"].iloc[-20:].to_numpy(float)
    pct = float((last <= current).mean() * 100)
    label = ("low" if pct < p["vix1d_low_below"] else "extreme" if pct >= p["vix1d_extreme_from"]
             else "high" if pct >= p["vix1d_high_from"] else "normal")
    return {"vix1d_pctile_20d": pct, "vix1d_20d_low": float(last.min()), "vix1d_20d_high": float(last.max()),
            "vix1d_label": label, "iv_high": label in ("high", "extreme")}


def extrinsic_remaining_pct(now_et: datetime, open_et: datetime, close_et: datetime) -> float:
    """ATM extrinsic remaining under a sqrt-of-time decay: sqrt(minutes left / session minutes) x 100."""
    total = (close_et - open_et).total_seconds()
    left = min(max((close_et - now_et).total_seconds(), 0.0), total)
    return math.sqrt(left / total) * 100 if total > 0 else 0.0


def theta_table(times_et: list[str], open_et: datetime, close_et: datetime) -> list[tuple[str, float]]:
    out = []
    for t in times_et:
        h, mi = map(int, t.split(":"))
        ts = open_et.replace(hour=h, minute=mi)
        if open_et <= ts <= close_et:
            out.append((t, round(extrinsic_remaining_pct(ts, open_et, close_et))))
    return out


def crush(straddle_now, straddle_0935, done_pct: float) -> dict:
    if not straddle_now or not straddle_0935:
        return {}
    ch = round((straddle_now / straddle_0935 - 1) * 100, 4)
    return {"iv_crush_pct": ch, "iv_crush_label": "crush done" if ch <= done_pct else "still elevated", "iv_crush_basis": "straddle vs 09:35 ET print"}


def crush_estimate_from_vix1d(m: Market, open_et: datetime, close_et: datetime, done_pct: float) -> dict:
    """No 09:35 straddle print: estimate the ATM straddle change as
    (VIX1D now / VIX1D at 09:35) x sqrt(time left now / time left at 09:35) - 1. An estimate, labelled as one."""
    df = m.intra.get("^VIX1D")
    if df is None or not len(df):
        return {}
    ref_t = open_et.replace(hour=9, minute=35)
    day = df[df.index >= open_et]
    ref = day[day.index >= ref_t]
    if not len(ref) or m.as_of <= ref_t:
        return {}
    v0, v1 = float(ref["c"].iloc[0]), float(day["c"].iloc[-1])
    t0 = (close_et - ref.index[0]).total_seconds()
    t1 = max((close_et - m.as_of).total_seconds(), 0.0)
    if v0 <= 0 or t0 <= 0:
        return {}
    ch = round((v1 / v0 * math.sqrt(t1 / t0) - 1) * 100, 4)
    return {"iv_crush_pct": ch, "iv_crush_label": "crush done" if ch <= done_pct else "still elevated",
            "iv_crush_basis": f"estimate: VIX1D {v0:g} at 09:35 ET to {v1:g} now, times sqrt(time left); no 09:35 straddle print"}
