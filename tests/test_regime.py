import copy
import json

import pytest

from digest import playbook
from digest.brief import Brief
from digest.regime import classify, load_rules

RULES = load_rules()


def variant(brief: Brief, **changes) -> Brief:
    """A copy of a real brief with dotted fields overridden, e.g. levels__gap_pct=0.8."""
    d = json.loads(brief.model_dump_json())
    for k, v in changes.items():
        sec, field = k.split("__")
        d[sec][field] = v
    return Brief(**d)


def label(b, rules=RULES, prior=None):
    return classify(b, rules, prior)


# --- the two real days ----------------------------------------------------------------

def test_2026_11_05_is_trend_down(brief_td_mid, brief_td_aft):
    for b in (brief_td_mid, brief_td_aft):
        assert b.regime.label == "trend_down"
        assert any("below prior value" in r for r in b.regime.rules_fired)
    assert brief_td_mid.regime.confirmation == "first classification"
    assert brief_td_aft.regime.confirmation == "confirmed" and brief_td_aft.regime.holding is True


def test_2026_11_06_is_balance(brief_mid):
    r = brief_mid.regime
    assert r.label == "balance" and len(r.rules_fired) >= 3
    assert brief_mid.levels.open_vs_prior_va == "inside" and brief_mid.intraday.vwap_crossed_both_ways


# --- each rule -------------------------------------------------------------------------

def test_before_classification_is_undetermined_with_a_lean(brief_pre):
    r = brief_pre.regime
    assert r.label == "undetermined" and "before the 10:30 ET classification" in r.rules_fired[0]
    assert r.lean in ("gap_up", "gap_down", "open_above_value", "open_below_value", "open_inside_value")


def test_market_closed_is_undetermined(brief_mid):
    r = label(variant(brief_mid, meta__market_closed_mode=True, meta__is_trading_day=False))
    assert r.label == "undetermined" and "market closed" in r.rules_fired[0]


def test_gap_and_go(brief_mid):
    r = label(variant(brief_mid, levels__gap_pct=0.8, intraday__snapshot_vs_or="above"))
    assert r.label == "gap_and_go"
    r = label(variant(brief_mid, levels__gap_pct=-0.8, intraday__snapshot_vs_or="below"))
    assert r.label == "gap_and_go"


def test_gap_and_fill(brief_mid):
    r = label(variant(brief_mid, levels__gap_pct=0.8, intraday__snapshot_vs_or="inside", intraday__snapshot_vs_prior_va="inside"))
    assert r.label == "gap_and_fill"


def test_gap_at_threshold_does_not_count(brief_mid):
    r = label(variant(brief_mid, levels__gap_pct=0.5, intraday__snapshot_vs_or="above"))
    assert r.label == "balance"  # falls through to the structure rule


def test_trend_up_and_down(brief_mid):
    up = variant(brief_mid, levels__open_vs_prior_va="above", intraday__vwap_crosses_by_cutoff=1, intraday__vwap_above_frac=0.9)
    assert label(up).label == "trend_up"
    dn = variant(brief_mid, levels__open_vs_prior_va="below", intraday__vwap_crosses_by_cutoff=0, intraday__vwap_above_frac=0.1)
    assert label(dn).label == "trend_down"


def test_trend_needs_vwap_respected_and_one_sided(brief_mid):
    two_cross = variant(brief_mid, levels__open_vs_prior_va="above", intraday__vwap_crosses_by_cutoff=2, intraday__vwap_above_frac=0.9)
    assert label(two_cross).label == "undetermined"
    wrong_side = variant(brief_mid, levels__open_vs_prior_va="above", intraday__vwap_crosses_by_cutoff=0, intraday__vwap_above_frac=0.2)
    assert label(wrong_side).label == "undetermined"


def test_balance_needs_two_way_vwap_and_symmetric_profile(brief_mid):
    assert label(variant(brief_mid, intraday__vwap_crosses_by_cutoff=1)).label == "undetermined"
    assert label(variant(brief_mid, intraday__dev_poc_position=0.9)).label == "undetermined"


def test_gap_day_that_neither_goes_nor_fills_is_undetermined(brief_mid):
    """The 2026-11-04 shape: +0.88% gap above prior value, inside the opening range at 10:30, VWAP crossed 3 times."""
    b = variant(brief_mid, levels__gap_pct=0.88, levels__open_vs_prior_va="above", intraday__snapshot_vs_or="inside",
                intraday__snapshot_vs_prior_va="above", intraday__vwap_crosses_by_cutoff=3, intraday__vwap_above_frac=0.89)
    r = label(b)
    assert r.label == "undetermined" and "no rule set is fully met" in r.rules_fired
    assert len(r.rules_failed) >= 3


def test_conflicting_rules_are_undetermined(brief_mid):
    b = variant(brief_mid, levels__gap_pct=0.8, intraday__snapshot_vs_or="above", levels__open_vs_prior_va="below",
                intraday__vwap_crosses_by_cutoff=0, intraday__vwap_above_frac=0.0)
    r = label(b)
    assert r.label == "undetermined" and r.conflicts


def test_missing_inputs_are_undetermined(brief_mid):
    r = label(variant(brief_mid, levels__prior_vah=None))
    assert r.label == "undetermined" and "data missing" in r.rules_fired[0]


def test_thresholds_come_from_yaml(brief_mid):
    b = variant(brief_mid, levels__gap_pct=0.8, intraday__snapshot_vs_or="above")
    assert label(b).label == "gap_and_go"
    rules = copy.deepcopy(RULES)
    rules["classify"]["gap_pct_min"] = 1.0
    assert label(b, rules).label == "balance"
    rules["classify"]["balance_min_vwap_crosses"] = 5
    assert label(b, rules).label == "undetermined"


def test_confirmed_and_changed(brief_td_aft):
    assert label(brief_td_aft, prior="trend_down").confirmation == "confirmed"
    assert label(brief_td_aft, prior="balance").confirmation == "changed"
    above_vwap = variant(brief_td_aft, levels__spot=brief_td_aft.intraday.vwap + 5)
    r = label(above_vwap, prior="trend_down")
    assert r.holding is False and r.confirmation == "changed"
    assert label(brief_td_aft).confirmation == "first classification"


# --- playbook --------------------------------------------------------------------------

def pb_for(b: Brief, **overrides):
    pb = copy.deepcopy(playbook.load_playbook())
    for k, v in overrides.items():
        sec, field = k.split("__")
        pb[sec][field] = v
    b = b.model_copy(deep=True)
    b.regime = classify(b, RULES, b.regime.prior_label)
    return playbook.evaluate(b, RULES, pb)


def test_premarket_playbook_is_pending(brief_pre):
    p = brief_pre.playbook
    assert p.live == "pending" and "10:30 ET / 07:30 PT" in p.early_status
    assert p.flip and p.do_not


def test_high_iv_balance_sits_out(brief_mid):
    assert brief_mid.vol.iv_high and brief_mid.regime.label == "balance"
    p = brief_mid.playbook
    assert p.live == "none" and "high IV on a balance day" in p.early_status and "high IV on a balance day" in p.late_status
    relaxed = pb_for(brief_mid, shared__sit_out_high_iv_balance=False)
    assert relaxed.live == "late" and "regime is balance" in relaxed.early_status


def test_high_iv_trend_is_early_with_debit_spread(brief_td_mid):
    b = brief_td_mid
    assert b.vol.iv_high and b.vol.iv_crush_label == "still elevated"
    p = b.playbook
    assert p.live == "early" and p.early_status == "live" and p.direction == "down" and p.instrument == "debit spread"
    assert "opening-range low" in p.early_trigger and "VWAP" in p.early_invalidation and p.early_time_stop_et == "13:00"


def test_normal_iv_trend_waits_for_the_crush(brief_td_mid):
    normal = variant(brief_td_mid, vol__iv_high=False, vol__vix1d_label="normal")
    p = pb_for(normal)
    assert p.live == "late" and "IV crush not done" in p.early_status and p.early_trigger is None
    done = variant(normal, vol__iv_crush_label="crush done", vol__iv_crush_pct=-25.0)
    p = pb_for(done)
    assert p.live == "early" and p.instrument == "single leg"
    unknown = variant(normal, vol__iv_crush_label=None, vol__iv_crush_pct=None)
    assert "unconfirmed" in pb_for(unknown).early_status


def test_afternoon_names_one_late_trigger(brief_td_aft):
    p = brief_td_aft.playbook
    assert p.live == "late" and p.early_status.startswith("window closed")
    assert p.late_status.startswith("armed") and p.late_trigger and "below" in p.late_trigger and "straight 5-min closes" in p.late_trigger
    assert p.premium_cap == playbook.NOT_SET and p.flat_by_et == "15:45"
    assert "counter-trend on gap-and-go" in p.do_not and "add to losers" in p.do_not


def test_premium_cap_comes_from_yaml_and_early_close_has_no_late_window(brief_td_aft):
    assert pb_for(brief_td_aft, late__premium_cap="3.00").premium_cap == "3.00"
    ec = variant(brief_td_aft, meta__is_early_close=True)
    p = pb_for(ec)
    assert p.live == "none" and "early close" in p.late_status


def test_unset_playbook_fields_stay_unset():
    pb = playbook.load_playbook()
    for sec in ("early", "late"):
        for k in ("sizing", "stop", "target", "max_trades"):
            assert pb[sec][k] is None, f"{sec}.{k} is the user's to set"
