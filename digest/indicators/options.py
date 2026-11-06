"""Option-chain statistics: ATM straddle (expected move), put/call ratios, top open-interest strikes.

Dealer gamma / GEX is deliberately not computed or estimated here.
"""
from __future__ import annotations

from digest import config


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


def compute_chain_stats(chain: dict, spot: float | None, fallback: bool) -> dict:
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
            out["straddle_strike"] = k * scale
            out["implied_range_low"] = (S - straddle) * scale
            out["implied_range_high"] = (S + straddle) * scale
        out["pcr_volume_0dte"], out["pcr_oi_0dte"] = put_call_ratios(z["calls"], z["puts"])
        out["call_oi_top_strikes"] = [s * scale for s in top_oi_strikes(z["calls"])]
        out["put_oi_top_strikes"] = [s * scale for s in top_oi_strikes(z["puts"])]
        walls = out["call_oi_top_strikes"] + out["put_oi_top_strikes"]
        if walls:
            spx_spot = S * scale
            near = min(walls, key=lambda w: abs(w - spx_spot))
            out["nearest_oi_strike"] = near
            out["spot_to_nearest_oi_strike_pts"] = spx_spot - near
    expw = chain.get("expiry_weekly")
    w = chain["chains"].get(expw) if expw else None
    if w:
        _, straddle_w = atm_straddle(w["calls"], w["puts"], S)
        out["weekly_expiry"] = expw
        if straddle_w:
            out["expected_move_weekly_pts"] = straddle_w * scale
            out["expected_move_weekly_pct"] = straddle_w / S * 100
    return out
