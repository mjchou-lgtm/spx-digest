"""Vol, cross-asset and breadth indicators from bars."""
from __future__ import annotations

from datetime import datetime

from digest import config
from digest.indicators import Market, annualized_rv_pct, pct

TERM_FLAT_BAND = 0.02  # |ratio - 1| within this band is labelled "flat"


def term_label(vix, vix3m):
    if not vix or not vix3m:
        return None
    r = vix / vix3m
    if r > 1 + TERM_FLAT_BAND:
        return "backwardation"
    if r < 1 - TERM_FLAT_BAND:
        return "contango"
    return "flat"


def _latest_or_prior(m: Market, t: str, session_open):
    v = m.latest(t, session_open)
    return v if v is not None else m.prior_close(t)


def compute_vol(m: Market, session_open: datetime) -> dict:
    out: dict = {}
    vals = {t: _latest_or_prior(m, t, session_open) for t in ["^VIX", "^VIX1D", "^VIX9D", "^VIX3M", "^VIX6M", "^VVIX", "^SKEW"]}
    out.update(vix=vals["^VIX"], vix1d=vals["^VIX1D"], vix9d=vals["^VIX9D"], vix3m=vals["^VIX3M"], vix6m=vals["^VIX6M"], vvix=vals["^VVIX"], skew=vals["^SKEW"])
    vix_prior = m.prior_close("^VIX")
    vix_now = m.latest("^VIX", session_open)
    if vix_now is not None and vix_prior:
        out["vix_change_pts"] = vix_now - vix_prior
        out["vix_change_pct"] = pct(vix_now, vix_prior)
    vv_now = m.latest("^VVIX", session_open)
    out["vvix_change_pct"] = pct(vv_now, m.prior_close("^VVIX"))
    if out["vix"] and out["vix9d"]:
        out["vix9d_vix_ratio"] = out["vix9d"] / out["vix"]
    if out["vix"] and out["vix3m"]:
        out["vix_vix3m_ratio"] = out["vix"] / out["vix3m"]
    out["term_structure_label"] = term_label(out["vix"], out["vix3m"])
    closes = m.hist(config.SPX)["c"] if len(m.hist(config.SPX)) else []
    out["rv10_pct"] = annualized_rv_pct(closes, 10)
    out["rv20_pct"] = annualized_rv_pct(closes, 20)
    if out["vix"] is not None and out["rv20_pct"] is not None:
        out["vix_minus_rv20_pts"] = out["vix"] - out["rv20_pct"]
    return out


def compute_cboe(cboe: dict | None) -> dict:
    if not cboe:
        return {}
    r = cboe.get("ratios", {})

    def f(name):
        try:
            return float(r[name])
        except (KeyError, TypeError, ValueError):
            return None

    return {
        "cboe_stats_date": cboe.get("date"),
        "cboe_total_pcr": f("TOTAL PUT/CALL RATIO"),
        "cboe_index_pcr": f("INDEX PUT/CALL RATIO"),
        "cboe_equity_pcr": f("EQUITY PUT/CALL RATIO"),
        "cboe_spx_pcr": f("SPX + SPXW PUT/CALL RATIO"),
    }


def compute_cross_asset(m: Market, session_open: datetime) -> dict:
    out: dict = {}
    # Futures trade overnight, so latest() needs no session gate.
    out["es_change_pct"] = m.change_pct("ES=F")
    out["nq_change_pct"] = m.change_pct("NQ=F")
    out["rty_change_pct"] = m.change_pct("RTY=F")
    tnx_now, tnx_prior = m.latest("^TNX", session_open), m.prior_close("^TNX")
    out["us10y_yield_pct"] = tnx_now if tnx_now is not None else tnx_prior
    if tnx_now is not None and tnx_prior is not None:
        out["us10y_change_bp"] = (tnx_now - tnx_prior) * 100
    out["us5y_yield_pct"] = _latest_or_prior(m, "^FVX", session_open)
    out["us3m_yield_pct"] = _latest_or_prior(m, "^IRX", session_open)
    for key, t in [("dxy", "DX-Y.NYB"), ("oil", "CL=F"), ("gold", "GC=F")]:
        out[key] = _latest_or_prior(m, t, None)
        out[f"{key}_change_pct"] = m.change_pct(t)
    return out


def compute_fred(fred: dict | None) -> dict:
    if not fred:
        return {}
    out: dict = {}
    as_of = None
    for series, field in [("DGS10", "fred_dgs10_pct"), ("DGS2", "fred_dgs2_pct"), ("T10Y2Y", "fred_t10y2y_pct"), ("DFF", "fred_dff_pct"), ("VIXCLS", "fred_vixcls")]:
        for o in fred.get(series, []):
            if o["value"] not in (".", "", None):
                out[field] = float(o["value"])
                as_of = max(as_of or o["date"], o["date"])
                break
    out["fred_as_of"] = as_of
    return out


def compute_breadth(m: Market, session_open: datetime) -> dict:
    # Pre-market: ETF/stock 5m bars include extended hours, so latest() is the pre-market print.
    ch = {t: m.change_pct(t) for t in [*config.ETFS, *config.SECTORS, *config.MEGACAPS]}
    out: dict = {
        "spy_change_pct": ch["SPY"],
        "rsp_change_pct": ch["RSP"],
        "qqq_change_pct": ch["QQQ"],
        "iwm_change_pct": ch["IWM"],
    }
    if ch["RSP"] is not None and ch["SPY"] is not None:
        out["rsp_minus_spy_pct"] = ch["RSP"] - ch["SPY"]
    if ch["QQQ"] is not None and ch["IWM"] is not None:
        out["qqq_minus_iwm_pct"] = ch["QQQ"] - ch["IWM"]
    sec = {t: round(ch[t], 2) for t in config.SECTORS if ch[t] is not None}
    out["sector_change_pct"] = sec
    out["sector_ranking"] = sorted(sec, key=sec.get, reverse=True)
    out["sectors_up_count"] = sum(1 for v in sec.values() if v > 0) if sec else None
    out["sectors_total"] = len(sec) or None
    mc = {t: round(ch[t], 2) for t in config.MEGACAPS if ch[t] is not None}
    out["megacap_change_pct"] = mc
    out["megacap_avg_change_pct"] = (sum(mc.values()) / len(mc)) if mc else None
    return out
