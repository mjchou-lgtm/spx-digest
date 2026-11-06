"""Which of the two playbooks is live, from the day type, the premium block and the clock.

Reports conditions only (read-only): the rules are the user's, in playbook.yaml. Nothing here
sizes, places or manages a position; unset fields are shown as "not set", never guessed.
"""
from __future__ import annotations

from datetime import datetime

import yaml

from digest import config
from digest.brief import Brief, Playbook
from digest.regime import direction
from digest.timefmt import both, tidy

NOT_SET = "not set (playbook.yaml)"


def load_playbook(path=config.PLAYBOOK_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _hhmm(dt: datetime) -> str:
    return dt.astimezone(config.ET).strftime("%H:%M")


def _nearest(b: Brief, side: str, confluence_only: bool = True):
    """Nearest stack level strictly above/below spot (confluence levels first)."""
    s = b.levels.spot
    cands = [l for l in b.levels.level_stack if (l.price > s if side == "above" else l.price < s) and l.kind not in ("vwap", "developing")]
    conf = [l for l in cands if l.confluence]
    pool = conf if (conf and confluence_only) else cands
    return min(pool, key=lambda l: abs(l.price - s)) if pool else None


def _flip(b: Brief, c: dict) -> list[str]:
    r, i, lv = b.regime, b.intraday, b.levels
    t = both(c["classify_time_et"])
    if r.label == "undetermined" and b.meta.post_type == "premarket":
        va = f"prior value ({lv.prior_val}–{lv.prior_vah})" if lv.prior_vah is not None else "prior value"
        if r.lean in ("gap_up", "gap_down"):
            side = "above" if r.lean == "gap_up" else "below"
            return [f"gap_and_go if spot is {side} the opening range at {t}",
                    f"gap_and_fill if spot is back inside {va} at {t}"]
        if r.lean in ("open_above_value", "open_below_value"):
            d = "up" if r.lean == "open_above_value" else "down"
            return [f"trend_{d} if the open stays outside {va} and VWAP is crossed fewer than 2 times by {both(c['vwap_cutoff_et'])}",
                    f"an open back inside {va} moves the day toward balance"]
        if r.lean == "open_inside_value":
            return [f"balance if VWAP is crossed both ways by {both(c['vwap_cutoff_et'])} with a symmetric developing profile",
                    f"an open outside {va} with VWAP respected moves the day toward trend"]
        return [f"classification at {t}"]
    if r.label in ("trend_up", "trend_down") and i.vwap is not None:
        return [f"5-min closes back {'below' if r.label == 'trend_up' else 'above'} VWAP {i.vwap}"]
    if r.label == "gap_and_go":
        return [f"a 5-min close back inside the opening range ({i.or_low}–{i.or_high})"]
    if r.label == "gap_and_fill":
        edge = i.or_high if (lv.gap_pct or 0) > 0 else i.or_low
        return [f"a reclaim of the opening-range {'high' if (lv.gap_pct or 0) > 0 else 'low'} {edge}"]
    if r.label == "balance":
        return [f"acceptance outside developing value ({i.dev_val}–{i.dev_vah}): {c['acceptance_closes']} consecutive 5-min closes beyond either edge"]
    return [x for x in r.rules_failed[:3]] or [f"classification at {t}"]


def evaluate(b: Brief, rules: dict, pb: dict | None = None) -> Playbook:
    out = _evaluate(b, rules, pb or load_playbook())
    for k in ("early_status", "early_trigger", "early_invalidation", "late_status", "late_trigger", "reasons", "flip"):
        setattr(out, k, tidy(getattr(out, k)))
    return out


def _evaluate(b: Brief, rules: dict, pb: dict) -> Playbook:
    sh, early, late = pb["shared"], pb["early"], pb["late"]
    c = rules["classify"]
    r, i, lv, vol = b.regime, b.intraday, b.levels, b.vol
    now = datetime.strptime(b.meta.as_of_pt, "%Y-%m-%d %H:%M").replace(tzinfo=config.PT)
    now_et = _hhmm(now)
    e0, e1 = early["window_et"]
    l0, l1 = late["window_et"]
    out = Playbook(
        live="none", early_window_et=f"{e0}–{e1}", early_time_stop_et=early["time_stop_et"], late_window_et=f"{l0}–{l1}",
        flat_by_et=sh["flat_by_et"], premium_cap=str(late["premium_cap"]) if late.get("premium_cap") is not None else NOT_SET,
        do_not=list(sh.get("never", [])), flip=_flip(b, c),
        instrument=(early["high_iv_instrument"] if vol.iv_high else "single leg"),
    )
    if b.meta.market_closed_mode:
        out.early_status = out.late_status = "not live: market closed"
        return out
    if b.meta.post_type == "premarket":
        out.live = "pending"
        out.early_status = f"pending: decided at the {both(c['classify_time_et'])} classification"
        out.early_trigger = (f"if the day classifies as {', '.join(early['regimes'])}"
                             + (" and the IV crush is done" if early.get("requires_iv_crush") else "")
                             + f": {c['acceptance_closes']} consecutive 5-min closes beyond the opening range in the regime direction")
        out.late_status = "not live: early close" if b.meta.is_early_close else f"window opens {both(l0)}; trigger is set in the afternoon post"
        out.reasons = [f"no trade until the {both(c['classify_time_et'])} classification"]
        return out

    d = direction(b, r.label) if r.holding is not False else None
    out.direction = d
    sit_out = bool(sh.get("sit_out_high_iv_balance") and vol.iv_high and r.label == "balance")

    # Early playbook.
    if now_et >= e1:
        out.early_status = f"window closed ({both(e1)})"
    elif sit_out:
        out.early_status = "not live: high IV on a balance day"
    elif r.label not in early["regimes"]:
        out.early_status = f"not live: regime is {r.label}"
    elif r.holding is False:
        out.early_status = f"not live: {r.label} is not holding ({r.holding_note})"
    elif (early.get("requires_iv_crush") and vol.iv_crush_label != "crush done"
          and not (early.get("high_iv_overrides_crush") and vol.iv_high)):
        out.early_status = ("not live: IV crush not done" if vol.iv_crush_label else "not live: IV crush unconfirmed (no 09:35 ET straddle print)")
    else:
        up = d == "up"
        edge, name = (i.or_high, "high") if up else (i.or_low, "low")
        out.early_status = "live" if now_et >= e0 else f"live from {both(e0)}"
        out.early_trigger = (f"{c['acceptance_closes']} consecutive 5-min closes {'above' if up else 'below'} the opening-range {name} {edge}"
                             f" (spot is {i.spot_vs_or} the opening range now)")
        out.early_invalidation = (f"a 5-min close back inside the opening range ({i.or_low}–{i.or_high})" if r.label == "gap_and_go"
                                  else f"a 5-min close back {'below' if up else 'above'} VWAP {i.vwap}")
    early_live = (out.early_status or "").startswith("live")

    # Late playbook.
    if b.meta.is_early_close:
        out.late_status = "not live: early close"
    elif now_et >= l1:
        out.late_status = f"window closed ({both(l1)})"
    elif sit_out:
        out.late_status = "not live: high IV on a balance day"
    elif lv.spot is None or i.dev_vah is None:
        out.late_status = "not live: developing value area unavailable"
    else:
        out.late_status = "live" if now_et >= l0 else f"armed: window opens {both(l0)}"
        n = c["acceptance_closes"]
        if d:
            side = "above" if d == "up" else "below"
            edge, ename = (i.dev_vah, "VAH") if d == "up" else (i.dev_val, "VAL")
            lvl = _nearest(b, side)
            use_edge = (edge > lv.spot) if d == "up" else (edge < lv.spot)
            if use_edge and (lvl is None or abs(edge - lv.spot) <= abs(lvl.price - lv.spot)):
                out.late_trigger = f"acceptance {side} developing {ename} {edge}: {n} consecutive 5-min closes beyond it"
            elif lvl is not None:
                out.late_trigger = (f"break {side} {lvl.name} {lvl.price}" + (f" (confluence with {lvl.confluence_with})" if lvl.confluence else "")
                                    + f" with volume returning (recent 5-min volume at least {rules['premium']['volume_returning_ratio']}x the 12:00–13:30 ET average)")
            else:
                out.late_trigger = f"acceptance {side} developing {ename} {edge}: {n} consecutive 5-min closes beyond it"
        else:
            up_d, dn_d = i.dev_vah - lv.spot, lv.spot - i.dev_val
            if i.accepted_outside_dev_va in ("above", "below"):
                out.late_trigger = (f"acceptance {i.accepted_outside_dev_va} developing value is in place "
                                    f"({i.dev_val}–{i.dev_vah}); it holds while 5-min closes stay outside")
            else:
                side, edge, ename = ("above", i.dev_vah, "VAH") if up_d <= dn_d else ("below", i.dev_val, "VAL")
                out.late_trigger = f"acceptance {side} developing {ename} {edge}: {n} consecutive 5-min closes beyond it (nearer edge)"
    late_on = (out.late_status or "").startswith(("live", "armed"))

    out.live = "early" if early_live else "late" if late_on else "none"
    if early_live:
        out.reasons.append(f"regime {r.label}; IV crush: {vol.iv_crush_label or 'unconfirmed'}"
                           + (f" ({vol.iv_crush_basis})" if vol.iv_crush_basis else ""))
    if vol.iv_high:
        out.reasons.append(f"VIX1D is {vol.vix1d_label} against its 20-day closes: instrument is {early['high_iv_instrument']}" if not sit_out
                           else f"VIX1D is {vol.vix1d_label} on a balance day: sit out")
    if r.label == "gap_and_go":
        out.reasons.append("gap-and-go: with-trend only")
    return out
