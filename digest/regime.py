"""Deterministic regime classification.

Each label is a set of named conditions. Thresholds and weights come from
regime_rules.yaml; this module only says *what* each condition compares.
A condition returns True/False, or None when its inputs are null or it does
not apply (e.g. opening-range rules in a premarket post). See the README
"Notes" section for the reasoning behind each rule.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import yaml

from digest import config
from digest.brief import Brief, Regime

Cond = Callable[[Brief, dict], Optional[bool]]


def load_rules(path=config.REGIME_RULES_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _all(*xs):
    return all(x is not None for x in xs)


def _get(b: Brief, dotted: str):
    sec, field = dotted.split(".")
    return getattr(getattr(b, sec), field)


# --- Conditions -------------------------------------------------------------------
# TREND_UP / TREND_DOWN

def _direction(sign: int) -> Cond:
    def f(b, p):
        s, pc = b.levels.spot, b.levels.prior_close
        return None if not _all(s, pc) else (s - pc) * sign > 0
    return f


def _gap_vs_em(sign: int) -> Cond:
    def f(b, p):
        g = b.levels.gap_em_fraction
        if g is None:
            return None
        return g >= p["gap_em_fraction_min"] if sign > 0 else g <= p["gap_em_fraction_max"]
    return f


def _holds_beyond_or(sign: int) -> Cond:
    def f(b, p):
        if b.meta.post_type == "premarket" or not b.intraday.or_complete or b.intraday.spot_vs_or is None:
            return None
        return b.intraday.spot_vs_or == ("above" if sign > 0 else "below")
    return f


def _vwap_side(sign: int) -> Cond:
    def f(b, p):
        d, atr = b.intraday.spot_minus_vwap_pts, b.levels.atr20_pts
        if b.meta.post_type == "premarket" or not _all(d, atr):
            return None
        return d * sign >= p["vwap_atr_frac"] * atr
    return f


def _breadth(sign: int) -> Cond:
    def f(b, p):
        n = b.breadth.sectors_up_count
        if n is None:
            return None
        return n >= p["sectors_up_min"] if sign > 0 else n <= p["sectors_up_max"]
    return f


def _equal_weight(sign: int) -> Cond:
    def f(b, p):
        d = b.breadth.rsp_minus_spy_pct
        if d is None:
            return None
        return d >= p["rsp_minus_spy_min_pct"] if sign > 0 else d <= p["rsp_minus_spy_max_pct"]
    return f


def _vix_opposite(sign: int) -> Cond:
    def f(b, p):
        v = b.vol.vix_change_pct
        if v is None:
            return None
        return v <= p["vix_change_pct_max"] if sign > 0 else v >= p["vix_change_pct_min"]
    return f


# RANGE

def inside_prior_range(b, p):
    s, hi, lo = b.levels.spot, b.levels.prior_high, b.levels.prior_low
    return None if not _all(s, hi, lo) else lo <= s <= hi


def small_gap(b, p):
    g = b.levels.gap_em_fraction
    return None if g is None else abs(g) < p["small_gap_em_fraction"]


def range_used_low(b, p):
    r = b.levels.range_used_atr_pct
    return None if b.meta.post_type == "premarket" or r is None else r < p["range_used_atr_pct_max"]


def near_oi_cluster(b, p):
    d, em = b.positioning.spot_to_nearest_oi_strike_pts, b.vol.expected_move_0dte_pts
    return None if not _all(d, em) else abs(d) <= p["oi_cluster_em_frac"] * em


def positive_gamma(b, p):
    side = b.positioning.spot_vs_gamma_flip
    return None if side is None else side == "above"


def near_vwap(b, p):
    d, atr = b.intraday.spot_minus_vwap_pts, b.levels.atr20_pts
    return None if b.meta.post_type == "premarket" or not _all(d, atr) else abs(d) <= p["vwap_atr_frac"] * atr


# EVENT_WAIT

def high_event_later(b, p):
    return bool(b.calendar.high_event_later_today)


def premium_rich_vs_rv(b, p):
    d = b.vol.vix_minus_rv20_pts
    return None if d is None else d >= p["vix_minus_rv20_min_pts"]


def em_rich_vs_rv(b, p):
    em_pts, spot, rv = b.vol.expected_move_day_pts, b.levels.spot, b.vol.rv20_pct
    if not _all(em_pts, spot, rv) or rv <= 0:
        return None
    return em_pts / spot * 100 >= p["em_vs_rv_ratio_min"] * (rv / math.sqrt(252))


def compressed_so_far(b, p):
    r = b.levels.range_used_atr_pct
    return None if b.meta.post_type == "premarket" or r is None else r < p["range_used_atr_pct_max"]


# VOL_EXPANSION

def front_backwardation(b, p):
    r = b.vol.vix9d_vix_ratio
    return None if r is None else r > p["vix9d_vix_ratio_min"]


def term_backwardation(b, p):
    r = b.vol.vix_vix3m_ratio
    return None if r is None else r > p["vix_vix3m_ratio_min"]


def vvix_spike(b, p):
    ch, lvl = b.vol.vvix_change_pct, b.vol.vvix
    if ch is None and lvl is None:
        return None
    return (ch is not None and ch >= p["vvix_change_pct_min"]) or (lvl is not None and lvl >= p["vvix_level_min"])


def vix_rising(b, p):
    v = b.vol.vix_change_pct
    return None if v is None else v >= p["vix_change_pct_min"]


def negative_gamma(b, p):
    side = b.positioning.spot_vs_gamma_flip
    return None if side is None else side == "below"


def range_expanded(b, p):
    r = b.levels.range_used_atr_pct
    return None if b.meta.post_type == "premarket" or r is None else r > p["range_used_atr_pct_min"]


CONDITIONS: dict[str, dict[str, Cond]] = {
    "TREND_UP": {
        "direction_up": _direction(+1), "gap_vs_em": _gap_vs_em(+1), "holds_beyond_or": _holds_beyond_or(+1),
        "above_vwap": _vwap_side(+1), "breadth_confirms": _breadth(+1), "equal_weight_confirms": _equal_weight(+1),
        "vix_opposite": _vix_opposite(+1),
    },
    "TREND_DOWN": {
        "direction_down": _direction(-1), "gap_vs_em": _gap_vs_em(-1), "holds_beyond_or": _holds_beyond_or(-1),
        "below_vwap": _vwap_side(-1), "breadth_confirms": _breadth(-1), "equal_weight_confirms": _equal_weight(-1),
        "vix_opposite": _vix_opposite(-1),
    },
    "RANGE": {
        "inside_prior_range": inside_prior_range, "small_gap": small_gap, "range_used_low": range_used_low,
        "near_oi_cluster": near_oi_cluster, "positive_gamma": positive_gamma, "near_vwap": near_vwap,
    },
    "EVENT_WAIT": {
        "high_event_later": high_event_later, "premium_rich_vs_rv": premium_rich_vs_rv,
        "em_rich_vs_rv": em_rich_vs_rv, "compressed_so_far": compressed_so_far,
    },
    "VOL_EXPANSION": {
        "front_backwardation": front_backwardation, "term_backwardation": term_backwardation,
        "vvix_spike": vvix_spike, "vix_rising": vix_rising, "negative_gamma": negative_gamma,
        "range_expanded": range_expanded,
    },
}

CONF_ORDER = ["low", "medium", "high"]


def _confidence(score: float, margin: float, rules: dict) -> str:
    c = rules["confidence"]
    if score >= c["high"]["min_score"] and margin >= c["high"]["min_margin"]:
        return "high"
    if score >= c["medium"]["min_score"] and margin >= c["medium"]["min_margin"]:
        return "medium"
    return "low"


def classify(b: Brief, rules: dict | None = None) -> Regime:
    rules = rules or load_rules()
    gates = rules["gates"]
    fired: list[str] = []

    # Gate 1: market closed (forced run on a non-trading day).
    if b.meta.market_closed_mode or not b.meta.is_trading_day:
        return Regime(label="NO_TRADE", confidence="high", rules_fired=["gate: market closed (not an NYSE session)"])
    # Gate 2: critical fields.
    missing_crit = [f for f in gates["critical_fields"] if _get(b, f) is None]
    if missing_crit:
        return Regime(label="NO_TRADE", confidence="high", rules_fired=[f"gate: critical data missing ({', '.join(missing_crit)})"])
    # Gate 3: too many important fields missing.
    missing_imp = [f for f in gates["important_fields"] if _get(b, f) is None]
    if len(missing_imp) > gates["max_important_missing"]:
        return Regime(label="NO_TRADE", confidence="medium",
                      rules_fired=[f"gate: data quality insufficient ({len(missing_imp)} important fields null: {', '.join(missing_imp)})"])

    scores: dict[str, float] = {}
    eligible: dict[str, float] = {}
    per_label_fired: dict[str, list[str]] = {}
    for label, spec in rules["labels"].items():
        fns = CONDITIONS[label]
        params = spec.get("params", {})
        met_w = eval_w = 0.0
        hits, required_ok = [], True
        for name, cfg in spec["conditions"].items():
            res = fns[name](b, params)
            w = float(cfg["weight"])
            if name in spec.get("required", []) and res is not True:
                required_ok = False
            if res is None:
                continue
            eval_w += w
            if res:
                met_w += w
                hits.append(f"{label}.{name}: {cfg['rule']}")
        score = met_w / eval_w if eval_w else 0.0
        scores[label] = round(score, 3)
        per_label_fired[label] = hits
        if required_ok and eval_w >= spec.get("min_evaluable_weight", 0):
            eligible[label] = score

    ranked = sorted(eligible.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked or ranked[0][1] < rules["min_score"]:
        best = f"{ranked[0][0]}={ranked[0][1]:.2f}" if ranked else "none eligible"
        return Regime(label="NO_TRADE", confidence="low", scores=scores,
                      rules_fired=[f"no label reached min_score {rules['min_score']} (best: {best})"])
    top, top_score = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - runner
    conf = _confidence(top_score, margin, rules)
    if conf == "low" and len(ranked) > 1 and margin < rules["conflict_margin"]:
        return Regime(label="NO_TRADE", confidence="low", scores=scores,
                      rules_fired=[f"conflicting signals: {top}={top_score:.2f} vs {ranked[1][0]}={ranked[1][1]:.2f} (margin < {rules['conflict_margin']})"])
    fired = per_label_fired[top]
    if b.meta.is_early_close:
        pen = int(gates.get("early_close_confidence_penalty", 1))
        conf = CONF_ORDER[max(0, CONF_ORDER.index(conf) - pen)]
        fired = fired + ["early close: confidence lowered"]
    return Regime(label=top, confidence=conf, rules_fired=fired, scores=scores)
