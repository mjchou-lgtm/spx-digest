import math
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from digest import config
from digest.indicators import Market, annualized_rv_pct, pct, r2
from digest.indicators import intraday as intr
from digest.indicators import levels, market_stats, options

ET = config.ET


# --- helpers ------------------------------------------------------------------------

def test_pct_and_round():
    assert pct(110, 100) == pytest.approx(10.0)
    assert pct(None, 100) is None and pct(1, 0) is None
    assert r2(float("nan")) is None and r2(1.23456) == 1.23


def test_annualized_rv_constant_returns_zero():
    closes = 100 * np.exp(np.arange(30) * 0.01)
    assert annualized_rv_pct(closes, 20) == pytest.approx(0.0, abs=1e-9)


def test_annualized_rv_known_value():
    r = np.array([0.01, -0.01] * 10)
    closes = 100 * np.exp(np.concatenate([[0], np.cumsum(r)]))
    expected = np.std(r, ddof=1) * math.sqrt(252) * 100
    assert annualized_rv_pct(closes, 20) == pytest.approx(expected)
    assert annualized_rv_pct(closes[:5], 20) is None


# --- levels -------------------------------------------------------------------------

def _daily(rows):
    df = pd.DataFrame(rows, columns=["o", "h", "l", "c"])
    df.index = [date(2026, 1, i + 1) for i in range(len(rows))]
    return df


def test_atr_true_range_uses_prior_close_gaps():
    d = _daily([[100, 101, 99, 100], [110, 111, 109, 110]])
    # TR on day 2 = max(2, |111-100|, |109-100|) = 11
    assert levels.true_range_atr(d, 1) == pytest.approx(11.0)
    assert levels.true_range_atr(d, 5) is None


def test_average_daily_range():
    d = _daily([[0, 10, 0, 5], [0, 20, 10, 15]])
    assert levels.average_daily_range(d, 2) == pytest.approx(10.0)


def test_levels_from_fixture(brief_mid):
    lv = brief_mid.levels
    assert lv.prior_date == "2026-11-03"
    assert lv.prior_low <= lv.prior_close <= lv.prior_high
    assert lv.session_low <= lv.spot <= lv.session_high
    assert lv.range_used_pts == pytest.approx(lv.session_high - lv.session_low, abs=0.02)
    assert lv.gap_pts == pytest.approx(lv.session_open - lv.prior_close, abs=0.02)
    assert lv.overnight_high >= lv.overnight_low
    assert lv.weekly_open == lv.monthly_open  # 2026-11-02 is the first session of both
    assert 0 < lv.atr20_pts < 400


def test_premarket_spot_is_es_implied(brief_pre):
    lv = brief_pre.levels
    assert brief_pre.meta.spot_source.startswith("ES-implied")
    assert lv.session_open is None and lv.range_used_pts is None
    assert any("ES-implied" in f for f in brief_pre.data_quality.fallbacks)


# --- options ------------------------------------------------------------------------

def _row(k, bid, ask, oi=0, vol=0, iv=0.2, last=None):
    return {"strike": k, "bid": bid, "ask": ask, "lastPrice": last, "openInterest": oi, "volume": vol, "impliedVolatility": iv}


def test_mid_price_falls_back_to_last():
    assert options.mid_price(_row(1, 1.0, 1.2)) == pytest.approx(1.1)
    assert options.mid_price(_row(1, 0, 0, last=2.5)) == 2.5
    assert options.mid_price(_row(1, 0, 0)) is None


def test_atm_straddle_picks_nearest_priced_strike():
    calls = [_row(95, 6, 6), _row(100, 2, 2), _row(105, 0.5, 0.5)]
    puts = [_row(95, 0.5, 0.5), _row(100, 2.5, 2.5), _row(105, 6, 6)]
    k, s = options.atm_straddle(calls, puts, 101)
    assert k == 100 and s == pytest.approx(4.5)


def test_put_call_ratios_and_top_oi():
    calls = [_row(100, 1, 1, oi=10, vol=4), _row(105, 1, 1, oi=30, vol=6)]
    puts = [_row(95, 1, 1, oi=20, vol=15)]
    pv, po = options.put_call_ratios(calls, puts)
    assert pv == pytest.approx(1.5) and po == pytest.approx(0.5)
    assert options.top_oi_strikes(calls, 1) == [105.0]


def test_bs_gamma_matches_closed_form():
    S, K, T, iv = 100.0, 100.0, 30 / 365, 0.2
    d1 = (math.log(S / K) + 0.5 * iv * iv * T) / (iv * math.sqrt(T))
    expected = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (S * iv * math.sqrt(T))
    assert float(options.bs_gamma(S, K, T, iv)) == pytest.approx(expected)


def test_gex_sign_and_flip():
    # Heavy put OI below, call OI above: GEX negative low, positive high -> one flip between.
    calls = [_row(105, 1, 1, oi=1000)]
    puts = [_row(95, 1, 1, oi=1000)]
    T = 1 / 365
    at_spot, flip = options.gex_profile(calls, puts, 100.0, T)
    assert flip is not None and 95 < flip < 105
    assert abs(flip - 100.0) < 1.0  # symmetric book -> flip near the midpoint
    net_low, _ = options.gex_profile(calls, puts, 96.0, T)
    assert net_low < 0


def test_chain_fallback_scales_strikes():
    calls = [_row(770, 1, 1, oi=50), _row(771, 0.6, 0.6, oi=10)]
    puts = [_row(770, 1.2, 1.2, oi=40), _row(769, 0.5, 0.5, oi=10)]
    chain = {"symbol": "SPY", "expiry_0dte": "2026-11-04", "expiry_weekly": None,
             "chains": {"2026-11-04": {"calls": calls, "puts": puts}}}
    now = datetime(2026, 11, 4, 10, 0, tzinfo=ET)
    close = datetime(2026, 11, 4, 16, 0, tzinfo=ET)
    out = options.compute_chain_stats(chain, 7702.0, now, close, fallback=True)
    assert out["chain_fallback_used"] is True
    assert out["expected_move_0dte_pts"] == pytest.approx(22.0)  # (1 + 1.2) x 10
    assert out["call_oi_top_strikes"][0] == 7700.0


def test_chain_stats_from_fixture(brief_mid):
    p, v = brief_mid.positioning, brief_mid.vol
    assert p.chain_source == "^SPX" and not p.chain_fallback_used
    assert v.expected_move_0dte_pts > 0 and v.expected_move_weekly_pts > v.expected_move_0dte_pts
    assert len(p.call_oi_top_strikes) == 5 and len(p.put_oi_top_strikes) == 5
    assert p.gamma_flip_approx is not None
    assert p.spot_vs_gamma_flip == ("above" if brief_mid.levels.spot >= p.gamma_flip_approx else "below")
    assert "approximate, OI-based" in p.gex_method


# --- vol / cross-asset / breadth ---------------------------------------------------

def test_term_label():
    assert market_stats.term_label(15, 18) == "contango"
    assert market_stats.term_label(25, 20) == "backwardation"
    assert market_stats.term_label(20, 20.1) == "flat"
    assert market_stats.term_label(None, 20) is None


def test_cboe_parse():
    out = market_stats.compute_cboe({"date": "2026-11-03", "ratios": {"TOTAL PUT/CALL RATIO": "0.86", "EQUITY PUT/CALL RATIO": "x"}})
    assert out["cboe_total_pcr"] == 0.86 and out["cboe_equity_pcr"] is None


def test_fred_parse_skips_missing_dots():
    out = market_stats.compute_fred({"DGS10": [{"date": "2026-11-03", "value": "."}, {"date": "2026-11-02", "value": "4.1"}]})
    assert out["fred_dgs10_pct"] == 4.1 and out["fred_as_of"] == "2026-11-02"


def test_vol_from_fixture(brief_mid):
    v = brief_mid.vol
    assert v.vix9d_vix_ratio == pytest.approx(v.vix9d / v.vix, abs=0.01)
    assert v.vix_vix3m_ratio == pytest.approx(v.vix / v.vix3m, abs=0.01)
    assert v.vix_minus_rv20_pts == pytest.approx(v.vix - v.rv20_pct, abs=0.02)
    assert v.cboe_total_pcr == 0.86


def test_breadth_from_fixture(brief_mid):
    b = brief_mid.breadth
    assert b.sectors_total == 11
    assert b.sectors_up_count == sum(1 for x in b.sector_change_pct.values() if x > 0)
    ranked = [b.sector_change_pct[s] for s in b.sector_ranking]
    assert ranked == sorted(ranked, reverse=True)
    assert b.rsp_minus_spy_pct == pytest.approx(b.rsp_change_pct - b.spy_change_pct, abs=0.02)


# --- intraday -------------------------------------------------------------------------

def _sess(prices, start=datetime(2026, 11, 4, 9, 30, tzinfo=ET)):
    idx = pd.date_range(start, periods=len(prices), freq="5min")
    p = np.asarray(prices, float)
    return pd.DataFrame({"o": p, "h": p + 1, "l": p - 1, "c": p, "v": 1.0}, index=idx)


def test_opening_range_and_position():
    s = _sess([100, 102, 101, 103, 99, 100, 110])
    hi, lo, done = intr.opening_range(s, s.index[0].to_pydatetime(), s.index[-1].to_pydatetime())
    assert (hi, lo, done) == (104, 98, True)
    assert intr.spot_vs_range(110, hi, lo) == "above"
    assert intr.spot_vs_range(100, hi, lo) == "inside"


def test_vwap_weights_by_proxy_volume():
    s = _sess([100, 200])
    proxy = s.copy()
    proxy["v"] = [3.0, 1.0]
    v, method = intr.vwap_with_proxy_volume(s, proxy)
    assert v == pytest.approx(125.0) and "SPY" in method


def test_retest_detection():
    up_down_up = _sess([100, 110, 100, 100, 100, 110])
    assert intr.retested(up_down_up, "high", tol_pts=1.0) is True
    one_way = _sess([100, 102, 104, 106, 108, 110])
    assert intr.retested(one_way, "high", tol_pts=1.0) is False


def test_intraday_from_fixture(brief_mid):
    i = brief_mid.intraday
    assert i.or_complete and i.or_high >= i.or_low
    assert i.spot_vs_or in ("inside", "above", "below")
    assert i.vwap is not None and i.rv_today_pct > 0


def test_premarket_has_no_intraday(brief_pre):
    assert brief_pre.intraday.or_high is None and brief_pre.intraday.vwap is None
    assert not any(f.startswith("intraday.") for f in brief_pre.data_quality.null_fields)
