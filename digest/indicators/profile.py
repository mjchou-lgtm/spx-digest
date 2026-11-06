"""Volume-at-price profile: POC, value area (70%), shape.

SPX has no volume, so each 5-minute SPX bar's range is weighted by SPY volume at the
same timestamp (the same proxy the VWAP uses). A bar's volume is spread evenly across
the price bins it spans. This is a coarse profile from 5-minute bars, not tick data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

METHOD = "SPX 5m bar ranges weighted by SPY 5m volume, 1-pt bins, 70% value area"
METHOD_SPY = "SPY 5m volume-at-price scaled to SPX by the close ratio, 70% value area"


def volume_profile(bars: pd.DataFrame, bin_size: float = 1.0, va_frac: float = 0.70) -> dict | None:
    """bars: columns h, l, v. Returns poc/vah/val, the range, and where the POC sits in it (0 = low, 1 = high)."""
    if bars is None or not len(bars):
        return None
    b = bars.dropna(subset=["h", "l"])
    v = b["v"].fillna(0.0).to_numpy(float)
    if not len(b) or v.sum() <= 0:
        return None
    lo, hi = float(b["l"].min()), float(b["h"].max())
    lo_edge = np.floor(lo / bin_size) * bin_size
    n = max(int(np.ceil((hi - lo_edge) / bin_size)), 1)
    hist = np.zeros(n)
    for h_, l_, v_ in zip(b["h"].to_numpy(float), b["l"].to_numpy(float), v):
        if v_ <= 0:
            continue
        i0 = int((l_ - lo_edge) // bin_size)
        i1 = min(max(int(np.ceil((h_ - lo_edge) / bin_size)) - 1, i0), n - 1)  # a high on a bin edge stays in the bin below
        hist[i0 : i1 + 1] += v_ / (i1 - i0 + 1)
    poc_i = int(np.argmax(hist))
    lo_i = hi_i = poc_i
    acc, total = hist[poc_i], hist.sum()
    while acc < va_frac * total and (lo_i > 0 or hi_i < n - 1):
        up = hist[hi_i + 1] if hi_i < n - 1 else -1.0
        dn = hist[lo_i - 1] if lo_i > 0 else -1.0
        if up >= dn:
            hi_i += 1
            acc += up
        else:
            lo_i -= 1
            acc += dn
    poc = lo_edge + (poc_i + 0.5) * bin_size
    val, vah = lo_edge + lo_i * bin_size, lo_edge + (hi_i + 1) * bin_size
    rng = hi - lo
    return {
        "poc": float(poc), "vah": float(min(vah, hi)), "val": float(max(val, lo)), "high": hi, "low": lo,
        "poc_position": float((poc - lo) / rng) if rng > 0 else 0.5,
        "va_width_frac": float((min(vah, hi) - max(val, lo)) / rng) if rng > 0 else 1.0,
    }


def profile_shape(p: dict | None, upper: float = 0.67, lower: float = 0.33, elongated_va_frac: float = 0.8) -> str | None:
    """D: POC mid-range. P: POC in the upper third. b: POC in the lower third.
    elongated: volume spread thin along the range (value area covers most of it)."""
    if not p:
        return None
    if p["va_width_frac"] >= elongated_va_frac:
        return "elongated"
    if p["poc_position"] >= upper:
        return "P"
    if p["poc_position"] <= lower:
        return "b"
    return "D"


def with_proxy_volume(price: pd.DataFrame, vol: pd.DataFrame | None) -> pd.DataFrame:
    """SPX price bars with the SPY volume at the same timestamps."""
    out = price[["h", "l", "c"]].copy()
    out["v"] = vol["v"].reindex(price.index).fillna(0.0) if vol is not None and len(vol) else 0.0
    return out


def session_profile(spx: pd.DataFrame, spy: pd.DataFrame | None, scale_close: float | None = None):
    """(profile, method). Falls back to SPY's own bars scaled to SPX points when SPX bars are missing."""
    if spx is not None and len(spx):
        p = volume_profile(with_proxy_volume(spx, spy))
        if p:
            return p, METHOD
    if spy is not None and len(spy) and scale_close:
        ratio = scale_close / float(spy["c"].iloc[-1])
        p = volume_profile(spy, bin_size=0.1)
        if p:
            return {k: (v * ratio if k in ("poc", "vah", "val", "high", "low") else v) for k, v in p.items()}, METHOD_SPY
    return None, None


def side_of(x, vah, val):
    if x is None or vah is None or val is None:
        return None
    return "above" if x > vah else "below" if x < val else "inside"
