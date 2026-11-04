"""Option-chain statistics: ATM straddle expected move, P/C, OI walls, approximate GEX and gamma flip.

GEX convention (standard public approximation, NOT dealer positioning):
    GEX_strike = OI x gamma x 100 x spot^2 x 0.01, calls positive, puts negative
i.e. dollar gamma per 1% move, assuming customers are long puts and short calls
against dealers — an assumption, which is why it is labelled "approximate, OI-based".
"""
from __future__ import annotations

import math
from datetime import datetime, time

import numpy as np
from scipy.stats import norm

from digest import config

MIN_T_MINUTES = 15.0
IV_MIN, IV_MAX = 0.02, 4.0


def mid_price(row: dict):
    b, a = row.get("bid") or 0.0, row.get("ask") or 0.0
    if b > 0 and a > 0 and a >= b:
        return (a + b) / 2.0
    lp = row.get("lastPrice")
    return lp if lp and lp > 0 else None


def atm_straddle(calls: list[dict], puts: list[dict], spot: float):
    """(strike, straddle price) at the listed strike nearest spot that has both legs priced."""
    pm = {p["strike"]: mid_price(p) for p in puts}
    best = None
    for c in calls:
        k = c["strike"]
        cm, p = mid_price(c), pm.get(k)
        if cm is None or p is None:
            continue
        d = abs(k - spot)
        if best is None or d < best[0]:
            best = (d, k, cm + p)
    if best is None:
        return None, None
    return best[1], best[2]


def put_call_ratios(calls: list[dict], puts: list[dict]):
    cv = sum(c.get("volume") or 0 for c in calls)
    pv = sum(p.get("volume") or 0 for p in puts)
    co = sum(c.get("openInterest") or 0 for c in calls)
    po = sum(p.get("openInterest") or 0 for p in puts)
    return (pv / cv if cv else None), (po / co if co else None)


def top_oi_strikes(rows: list[dict], n: int = 5) -> list[float]:
    ranked = sorted((r for r in rows if (r.get("openInterest") or 0) > 0), key=lambda r: r["openInterest"], reverse=True)
    return [float(r["strike"]) for r in ranked[:n]]


def years_to_close(now_et: datetime, close_et: datetime) -> float:
    minutes = max((close_et - now_et).total_seconds() / 60.0, MIN_T_MINUTES)
    return minutes / (365.0 * 24 * 60)


def bs_gamma(S, K, T, iv):
    S, K, iv = np.asarray(S, float), np.asarray(K, float), np.asarray(iv, float)
    sq = iv * math.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * iv * iv * T) / sq
    return norm.pdf(d1) / (S * sq)


def _clean_iv(rows: list[dict], spot: float) -> np.ndarray:
    iv = np.array([r.get("impliedVolatility") or np.nan for r in rows], float)
    ok = (iv > IV_MIN) & (iv < IV_MAX)
    k = np.array([r["strike"] for r in rows], float)
    near = ok & (abs(k - spot) / spot < 0.02)
    fill = np.nanmedian(iv[near]) if near.any() else (np.nanmedian(iv[ok]) if ok.any() else 0.2)
    return np.where(ok, iv, fill)


def gex_profile(calls: list[dict], puts: list[dict], spot: float, T: float):
    """Arrays for GEX as a function of hypothetical spot; returns (net_at_spot_usd, flip_level)."""
    ck = np.array([c["strike"] for c in calls], float)
    pk = np.array([p["strike"] for p in puts], float)
    coi = np.array([c.get("openInterest") or 0 for c in calls], float)
    poi = np.array([p.get("openInterest") or 0 for p in puts], float)
    civ, piv = _clean_iv(calls, spot), _clean_iv(puts, spot)

    def net(S):
        g_c = bs_gamma(S, ck, T, civ) * coi
        g_p = bs_gamma(S, pk, T, piv) * poi
        return float((g_c.sum() - g_p.sum()) * 100 * S * S * 0.01)

    at_spot = net(spot)
    grid = spot * np.linspace(0.95, 1.05, 201)
    vals = np.array([net(s) for s in grid])
    flips = []
    for i in range(len(grid) - 1):
        a, b = vals[i], vals[i + 1]
        if a == 0 or (a < 0) != (b < 0):
            x = grid[i] if a == b else grid[i] + (grid[i + 1] - grid[i]) * (-a) / (b - a)
            flips.append(float(x))
    flip = min(flips, key=lambda x: abs(x - spot)) if flips else None
    return at_spot, flip


def compute_chain_stats(chain: dict, spot: float | None, now_et: datetime, close_et: datetime, fallback: bool) -> dict:
    """chain: raw payload from fetch_option_chain. Returns brief fields (vol EM + positioning)."""
    out: dict = {"chain_source": chain.get("symbol"), "chain_fallback_used": fallback}
    scale = config.CHAIN_FALLBACK_SCALE if fallback else 1.0
    und = chain.get("underlying_price")
    # Work in the chain's own units, then scale strikes/points to SPX.
    S = (spot / scale) if spot else und
    if not S:
        return out
    exp0 = chain.get("expiry_0dte")
    out["expiry_0dte"] = exp0
    z = chain["chains"].get(exp0) if exp0 else None
    if z:
        k, straddle = atm_straddle(z["calls"], z["puts"], S)
        if straddle:
            out["expected_move_0dte_pts"] = straddle * scale
            out["expected_move_0dte_pct"] = straddle / S * 100
        out["pcr_volume_0dte"], out["pcr_oi_0dte"] = put_call_ratios(z["calls"], z["puts"])
        out["call_oi_top_strikes"] = [s * scale for s in top_oi_strikes(z["calls"])]
        out["put_oi_top_strikes"] = [s * scale for s in top_oi_strikes(z["puts"])]
        walls = out["call_oi_top_strikes"] + out["put_oi_top_strikes"]
        if walls:
            spx_spot = S * scale
            near = min(walls, key=lambda w: abs(w - spx_spot))
            out["nearest_oi_strike"] = near
            out["spot_to_nearest_oi_strike_pts"] = spx_spot - near
        T = years_to_close(now_et, close_et)
        net, flip = gex_profile(z["calls"], z["puts"], S, T)
        out["net_gex_at_spot_usd_bn"] = net / 1e9
        if flip is not None:
            out["gamma_flip_approx"] = flip * scale
            out["spot_vs_gamma_flip_pts"] = (S - flip) * scale
            out["spot_vs_gamma_flip"] = "above" if S >= flip else "below"
    expw = chain.get("expiry_weekly")
    w = chain["chains"].get(expw) if expw else None
    if w:
        _, straddle_w = atm_straddle(w["calls"], w["puts"], S)
        out["weekly_expiry"] = expw
        if straddle_w:
            out["expected_move_weekly_pts"] = straddle_w * scale
            out["expected_move_weekly_pct"] = straddle_w / S * 100
    return out
