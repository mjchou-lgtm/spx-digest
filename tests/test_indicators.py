import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from digest import config
from digest.indicators import Market, annualized_rv_pct, pct, r2
from digest.indicators import intraday as intr
from digest.indicators import levels, market_stats, options, premium, profile

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
    assert lv.prior_date == "2026-11-05"
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


def test_chain_fallback_scales_strikes():
    calls = [_row(770, 1, 1, oi=50), _row(771, 0.6, 0.6, oi=10)]
    puts = [_row(770, 1.2, 1.2, oi=40), _row(769, 0.5, 0.5, oi=10)]
    chain = {"symbol": "SPY", "expiry_0dte": "2026-11-04", "expiry_weekly": None,
             "chains": {"2026-11-04": {"calls": calls, "puts": puts}}}
    out = options.compute_chain_stats(chain, 7702.0, fallback=True)
    assert out["chain_fallback_used"] is True
    assert out["expected_move_0dte_pts"] == pytest.approx(22.0)  # (1 + 1.2) x 10
    assert out["straddle_strike"] == 7700.0
    assert out["implied_range_low"] == pytest.approx(7680.0) and out["implied_range_high"] == pytest.approx(7724.0)
    assert out["call_oi_top_strikes"][0] == 7700.0
    assert not any("gex" in k or "gamma" in k for k in out), "dealer gamma is not computed"


def test_chain_stats_from_fixture(brief_mid):
    p, v = brief_mid.positioning, brief_mid.vol
    assert p.chain_source == "^SPX" and not p.chain_fallback_used
    assert v.expected_move_0dte_pts > 0 and v.expected_move_weekly_pts > v.expected_move_0dte_pts
    assert len(p.call_oi_top_strikes) == 5 and len(p.put_oi_top_strikes) == 5
    assert v.implied_range_low < brief_mid.levels.spot < v.implied_range_high
    assert v.implied_range_high - v.implied_range_low == pytest.approx(2 * v.expected_move_0dte_pts, abs=0.05)
    assert v.straddle_quote_time_et == "11:25"
    assert p.gex_vendor_url is None and not any("gamma" in k for k in type(p).model_fields)


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
    assert v.cboe_total_pcr is not None


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


# --- volume profile -------------------------------------------------------------------

def _bars(rows):
    df = pd.DataFrame(rows, columns=["l", "h", "v"])
    df["c"] = df["h"]
    df.index = pd.date_range(datetime(2026, 11, 4, 9, 30, tzinfo=ET), periods=len(rows), freq="5min")
    return df


def test_volume_profile_poc_and_value_area():
    # Most volume trades 100-102; thin tails either side.
    p = profile.volume_profile(_bars([(95, 96, 10), (100, 102, 500), (100, 102, 500), (105, 106, 10)]))
    assert 100 <= p["poc"] <= 102
    assert p["val"] >= 100 and p["vah"] <= 102  # 70% of the volume sits in the heavy node
    assert p["low"] == 95 and p["high"] == 106
    assert profile.volume_profile(_bars([(1, 2, 0)])) is None


def test_value_area_holds_about_70_percent():
    rows = [(100 + i, 101 + i, v) for i, v in enumerate([1, 2, 4, 8, 16, 8, 4, 2, 1])]
    p = profile.volume_profile(_bars(rows))
    inside = sum(v for (l, h, v) in rows if l >= p["val"] and h <= p["vah"])
    assert inside / sum(v for *_, v in rows) >= 0.70
    assert p["poc"] == pytest.approx(104.5)


def test_profile_shapes():
    assert profile.profile_shape({"poc_position": 0.5, "va_width_frac": 0.4}) == "D"
    assert profile.profile_shape({"poc_position": 0.8, "va_width_frac": 0.4}) == "P"
    assert profile.profile_shape({"poc_position": 0.1, "va_width_frac": 0.4}) == "b"
    assert profile.profile_shape({"poc_position": 0.5, "va_width_frac": 0.9}) == "elongated"
    assert profile.side_of(105, 104, 100) == "above" and profile.side_of(102, 104, 100) == "inside" and profile.side_of(None, 1, 0) is None


def test_prior_value_area_from_fixture(brief_mid):
    lv = brief_mid.levels
    assert lv.prior_low <= lv.prior_val < lv.prior_poc < lv.prior_vah <= lv.prior_high
    assert "70% value area" in lv.value_area_method
    assert lv.open_vs_prior_va == profile.side_of(lv.session_open, lv.prior_vah, lv.prior_val)


# --- VWAP crosses and the 10:30 snapshot ----------------------------------------------------

def test_vwap_cross_count():
    s = _sess([100, 101, 102, 103])           # one-way: every close above the running VWAP after the first bar
    n, frac = intr.vwap_crosses(s, intr.running_vwap(s, s))
    assert n == 0
    s = _sess([100, 104, 96, 104, 96])          # whipsaw
    n, frac = intr.vwap_crosses(s, intr.running_vwap(s, s))
    assert n >= 3 and 0 < frac < 1


def test_structure_from_fixture(brief_mid, brief_td_mid):
    i = brief_mid.intraday
    assert i.snapshot_time_et == "10:30" and i.vwap_cutoff_et == "11:00" and i.vwap_check_final is True
    assert i.vwap_crosses >= i.vwap_crosses_by_cutoff
    assert i.dev_val <= i.dev_poc <= i.dev_vah and 0 <= i.dev_poc_position <= 1
    t = brief_td_mid.intraday  # 10:45 ET replay: the 11:00 cutoff has not passed
    assert t.vwap_check_final is False and t.vwap_crosses_by_cutoff == 0 and t.vwap_above_frac == 0
    assert t.snapshot_vs_or == "below" and t.snapshot_vs_prior_va == "below"


# --- level stack ------------------------------------------------------------------------

def test_level_stack_marks_confluence_and_sorts():
    lv = {"spot": 7400.0, "prior_high": 7452.0, "prior_low": 7300.0, "prior_close": 7398.0, "prior_vah": 7449.0}
    stack, rounds = levels.build_level_stack(lv, {}, tol_pts=5, round_step=50, reach_pts=60)
    prices = [x["price"] for x in stack]
    assert prices == sorted(prices, reverse=True)
    assert rounds == [7350.0, 7400.0, 7450.0]
    by = {x["name"]: x for x in stack}
    assert by["prior high"]["confluence"] and "prior VAH" in by["prior high"]["confluence_with"] and "round 7450" in by["prior high"]["confluence_with"]
    assert not by["prior low"]["confluence"]
    assert by["round 7400"]["confluence_with"] == "prior close"


def test_level_stack_from_fixture(brief_pre, brief_mid):
    names = {l.name for l in brief_pre.levels.level_stack}
    assert {"prior high", "prior low", "prior close", "prior VAH", "prior POC", "prior VAL", "O/N high", "O/N low"} <= names
    assert any(n.startswith("round ") for n in names) and not any(n.startswith(("OR ", "dev ")) for n in names)
    assert {"OR high", "OR low", "VWAP", "dev VAH", "dev VAL"} <= {l.name for l in brief_mid.levels.level_stack}


# --- premium ----------------------------------------------------------------------------

def test_theta_table_matches_the_sqrt_of_time_reference():
    o, c = datetime(2026, 11, 4, 9, 30, tzinfo=ET), datetime(2026, 11, 4, 16, 0, tzinfo=ET)
    table = premium.theta_table(["10:30", "11:30", "12:30", "13:30", "14:30", "15:30"], o, c)
    assert table == [("10:30", 92), ("11:30", 83), ("12:30", 73), ("13:30", 62), ("14:30", 48), ("15:30", 28)]
    assert premium.extrinsic_remaining_pct(o, o, c) == 100 and premium.extrinsic_remaining_pct(c, o, c) == 0


def test_crush_threshold():
    assert premium.crush(40.0, 50.0, -20)["iv_crush_label"] == "crush done"       # exactly -20%
    assert premium.crush(41.0, 50.0, -20)["iv_crush_label"] == "still elevated"
    assert premium.crush(None, 50.0, -20) == {} and premium.crush(40.0, None, -20) == {}


def test_vix1d_percentile_and_label(brief_mid):
    v = brief_mid.vol
    assert v.vix1d is not None and 0 <= v.vix1d_pctile_20d <= 100
    assert v.vix1d_20d_low <= v.vix1d_20d_high
    assert v.iv_high == (v.vix1d_label in ("high", "extreme"))
    assert 0 < v.theta_extrinsic_remaining_pct < 100


def test_crush_uses_the_0935_print_when_there_is_one(raw_mid):
    from digest.pipeline import build_brief

    r = json.loads(json.dumps(raw_mid))
    r["context"] = {"straddle_0935": {"pts": 80.0, "time_et": "09:36", "source": "manual"}}
    v = build_brief(r).vol
    assert v.straddle_0935_pts == 80.0 and v.straddle_0935_source == "manual"
    assert v.iv_crush_pct == pytest.approx((v.expected_move_0dte_pts / 80.0 - 1) * 100, abs=0.01)
    assert v.iv_crush_label == "crush done" and v.iv_crush_basis.startswith("straddle")
    assert v.expected_move_day_pts == 80.0


def test_crush_without_a_print_is_a_labelled_estimate(brief_mid):
    v = brief_mid.vol
    assert v.straddle_0935_pts is None and v.iv_crush_basis.startswith("estimate")
    assert any("estimate" in f for f in brief_mid.data_quality.fallbacks)
    assert any("09:35" in m for m in brief_mid.data_quality.manual_inputs)
