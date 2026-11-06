"""Deterministic day-type classification from the brief. Thresholds: regime_rules.yaml."""
from __future__ import annotations

import yaml

from digest import config
from digest.brief import Brief, Regime
from digest.timefmt import tidy


def load_rules(path=config.REGIME_RULES_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def lean(b: Brief, c: dict) -> str | None:
    """Pre-classification lean from the gap and where the (indicated) open sits against prior value."""
    g, side = b.levels.gap_pct, b.levels.open_vs_prior_va
    if g is not None and abs(g) > c["gap_pct_min"]:
        return "gap_up" if g > 0 else "gap_down"
    return {"above": "open_above_value", "below": "open_below_value", "inside": "open_inside_value"}.get(side)


def _gap_rule(b: Brief, c: dict, fired: list, failed: list) -> str | None:
    g = b.levels.gap_pct
    if abs(g) <= c["gap_pct_min"]:
        failed.append(f"gap rules: gap {g:+.2f}% is within ±{c['gap_pct_min']}%")
        return None
    up = g > 0
    t, i = c["classify_time_et"], b.intraday
    fired.append(f"gap {g:+.2f}% (beyond ±{c['gap_pct_min']}%)")
    if i.snapshot_vs_or == ("above" if up else "below"):
        fired.append(f"gap_and_go: {i.snapshot_spot} at {t} ET, {i.snapshot_vs_or} the opening range {i.or_low}–{i.or_high}")
        return "gap_and_go"
    failed.append(f"gap_and_go: {i.snapshot_spot} at {t} ET, {i.snapshot_vs_or} the opening range {i.or_low}–{i.or_high}")
    if i.snapshot_vs_prior_va == "inside":
        fired.append(f"gap_and_fill: {i.snapshot_spot} at {t} ET, back inside prior value {b.levels.prior_val}–{b.levels.prior_vah}")
        return "gap_and_fill"
    failed.append(f"gap_and_fill: {i.snapshot_spot} at {t} ET, {i.snapshot_vs_prior_va} prior value {b.levels.prior_val}–{b.levels.prior_vah}")
    return None


def _structure_rule(b: Brief, c: dict, fired: list, failed: list) -> str | None:
    i, lv = b.intraday, b.levels
    n, frac, side = i.vwap_crosses_by_cutoff, i.vwap_above_frac, lv.open_vs_prior_va
    by = f"by {i.vwap_cutoff_et} ET" if i.vwap_check_final else f"so far (final {i.vwap_cutoff_et} ET)"
    va = f"prior value {lv.prior_val}–{lv.prior_vah}"
    if side in ("above", "below"):
        respected = n <= c["trend_max_vwap_crosses"]
        want_frac = frac >= c["one_sided_min_frac"] if side == "above" else frac <= 1 - c["one_sided_min_frac"]
        msgs = [
            (True, f"open {lv.session_open} {side} {va}"),
            (respected, f"VWAP crossed {n}× {by} (needs < {c['trend_max_vwap_crosses'] + 1})"),
            (want_frac, f"{frac * 100:.0f}% of closes above VWAP (needs "
                        f"{'≥' if side == 'above' else '≤'} {(c['one_sided_min_frac'] if side == 'above' else 1 - c['one_sided_min_frac']) * 100:.0f}%)"),
        ]
        label = f"trend_{'up' if side == 'above' else 'down'}"
        for met, m in msgs:
            (fired if met else failed).append(f"{label}: {m}")
        return label if respected and want_frac else None
    both = n >= c["balance_min_vwap_crosses"]
    pos = i.dev_poc_position
    sym = pos is not None and c["profile_lower"] <= pos <= c["profile_upper"]
    msgs = [
        (True, f"open {lv.session_open} inside {va}"),
        (both, f"VWAP crossed {n}× {by} (needs ≥ {c['balance_min_vwap_crosses']})"),
        (sym, f"developing POC {i.dev_poc} at {pos * 100:.0f}% of the range (needs "
              f"{c['profile_lower'] * 100:.0f}–{c['profile_upper'] * 100:.0f}%)" if pos is not None else "developing profile unavailable"),
    ]
    for met, m in msgs:
        (fired if met else failed).append(f"balance: {m}")
    return "balance" if both and sym else None


DIRECTION = {"trend_up": "up", "trend_down": "down"}


def direction(b: Brief, label: str) -> str | None:
    if label in DIRECTION:
        return DIRECTION[label]
    if label == "gap_and_go" and b.levels.gap_pct is not None:
        return "up" if b.levels.gap_pct > 0 else "down"
    return None


def _holding(b: Brief, label: str) -> tuple[bool | None, str | None]:
    """Is the 10:30 ET label still supported by where price is now?"""
    i, lv, s = b.intraday, b.levels, b.levels.spot
    if s is None:
        return None, None
    if label in ("trend_up", "trend_down") and i.vwap is not None:
        ok = s > i.vwap if label == "trend_up" else s < i.vwap
        return ok, f"spot {s} {'above' if s > i.vwap else 'below'} VWAP {i.vwap}"
    if label == "gap_and_go" and i.spot_vs_or:
        want = "above" if lv.gap_pct > 0 else "below"
        return i.spot_vs_or == want, f"spot {s} {i.spot_vs_or} the opening range {i.or_low}–{i.or_high}"
    if label == "gap_and_fill" and i.spot_vs_or:
        against = "above" if lv.gap_pct > 0 else "below"
        return i.spot_vs_or != against, f"spot {s} {i.spot_vs_or} the opening range {i.or_low}–{i.or_high}"
    if label == "balance" and i.accepted_outside_dev_va:
        ok = i.accepted_outside_dev_va == "no"
        return ok, (f"no acceptance outside developing value {i.dev_val}–{i.dev_vah}" if ok
                    else f"accepted {i.accepted_outside_dev_va} developing value {i.dev_val}–{i.dev_vah}")
    return None, None


def classify(b: Brief, rules: dict | None = None, prior_label: str | None = None) -> Regime:
    rules = rules or load_rules()
    c = rules["classify"]
    t = c["classify_time_et"]
    if b.meta.market_closed_mode or not b.meta.is_trading_day:
        return Regime(label="undetermined", rules_fired=["market closed (not an NYSE session)"])
    ln = lean(b, c)
    i, lv = b.intraday, b.levels
    if b.meta.post_type == "premarket" or i.snapshot_spot is None:
        return Regime(label="undetermined", lean=ln, rules_fired=[f"before the {t} ET classification"])
    need = {"levels.gap_pct": lv.gap_pct, "levels.prior_vah": lv.prior_vah, "levels.prior_val": lv.prior_val,
            "levels.session_open": lv.session_open, "intraday.or_high": i.or_high,
            "intraday.vwap_crosses_by_cutoff": i.vwap_crosses_by_cutoff, "intraday.vwap_above_frac": i.vwap_above_frac}
    missing = [k for k, v in need.items() if v is None]
    if missing:
        return Regime(label="undetermined", lean=ln, rules_fired=[f"data missing: {', '.join(missing)}"])

    fired: list[str] = []
    failed: list[str] = []
    conflicts: list[str] = []
    gap_label = _gap_rule(b, c, fired, failed)
    struct_label = _structure_rule(b, c, fired, failed)
    label = gap_label or struct_label or "undetermined"
    if gap_label == "gap_and_go" and struct_label in DIRECTION and DIRECTION[struct_label] != direction(b, "gap_and_go"):
        conflicts.append(f"gap_and_go ({direction(b, 'gap_and_go')}) conflicts with {struct_label}")
        label = "undetermined"
    if label == "undetermined" and not conflicts:
        fired.append("no rule set is fully met")
    if not i.vwap_check_final:
        fired.append(f"provisional until {i.vwap_cutoff_et} ET (VWAP count)")

    holding, note = (None, None) if label == "undetermined" else _holding(b, label)
    if prior_label is None or prior_label == "undetermined":
        confirmation = "first classification"
    else:
        confirmation = "confirmed" if (label == prior_label and holding is not False) else "changed"
    return Regime(label=label, lean=ln, rules_fired=tidy(fired), rules_failed=tidy(failed), conflicts=conflicts,
                  prior_label=prior_label, confirmation=confirmation, holding=holding, holding_note=tidy(note))
