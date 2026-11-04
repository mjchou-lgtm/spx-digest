import copy
import json
from pathlib import Path

import pytest

from digest.brief import Brief
from digest.regime import CONDITIONS, classify, load_rules

BRIEFS = Path(__file__).parent / "fixtures" / "briefs"
LABELS = ["TREND_UP", "TREND_DOWN", "RANGE", "EVENT_WAIT", "VOL_EXPANSION", "NO_TRADE"]


def load(label) -> dict:
    return json.loads((BRIEFS / f"{label}.json").read_text())


@pytest.mark.parametrize("label", LABELS)
def test_fixture_brief_produces_its_label(label):
    r = classify(Brief(**load(label)))
    assert r.label == label
    assert r.rules_fired, "every result must say which rules fired"


def test_every_yaml_condition_is_implemented():
    rules = load_rules()
    for label, spec in rules["labels"].items():
        assert set(spec["conditions"]) == set(CONDITIONS[label]), label
        for req in spec.get("required", []):
            assert req in spec["conditions"]


def test_market_closed_gate():
    b = load("TREND_UP")
    b["meta"]["market_closed_mode"] = True
    b["meta"]["is_trading_day"] = False
    r = classify(Brief(**b))
    assert r.label == "NO_TRADE" and "market closed" in r.rules_fired[0]


def test_data_quality_gate_counts_important_fields():
    b = load("TREND_UP")
    for sec, f in [("vol", "expected_move_0dte_pts"), ("levels", "atr20_pts"), ("vol", "vix9d"), ("vol", "vix3m")]:
        b[sec][f] = None
    r = classify(Brief(**b))
    assert r.label == "NO_TRADE" and "data quality" in r.rules_fired[0]


def test_early_close_lowers_confidence_one_notch():
    b = load("TREND_UP")
    assert classify(Brief(**b)).confidence == "high"
    b["meta"]["is_early_close"] = True
    r = classify(Brief(**b))
    assert r.label == "TREND_UP" and r.confidence == "medium"
    assert "early close" in r.rules_fired[-1]


def test_conflicting_signals_become_no_trade():
    rules = copy.deepcopy(load_rules())
    # Make every label equally (and weakly) supported by forcing a tie through the thresholds.
    rules["min_score"] = 0.0
    rules["confidence"]["medium"]["min_margin"] = 0.99
    rules["confidence"]["high"]["min_margin"] = 0.99
    rules["conflict_margin"] = 1.01
    r = classify(Brief(**load("RANGE")), rules)
    assert r.label == "NO_TRADE" and "conflicting" in r.rules_fired[0]


def test_thresholds_come_from_yaml():
    rules = copy.deepcopy(load_rules())
    b = Brief(**load("VOL_EXPANSION"))
    assert classify(b, rules).label == "VOL_EXPANSION"
    p = rules["labels"]["VOL_EXPANSION"]["params"]
    p.update(vix9d_vix_ratio_min=5, vix_vix3m_ratio_min=5, vvix_change_pct_min=500, vvix_level_min=500,
             vix_change_pct_min=500, range_used_atr_pct_min=5000)
    assert classify(b, rules).label != "VOL_EXPANSION"


def test_premarket_skips_intraday_conditions(brief_pre):
    # Opening-range / VWAP / range-used rules are not evaluable before the open.
    r = brief_pre.regime
    assert not any("holds_beyond_or" in x or "vwap" in x or "range_used" in x for x in r.rules_fired)
