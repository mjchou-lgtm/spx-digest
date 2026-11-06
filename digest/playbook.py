"""Which of the two playbooks is live, from the day type, the premium block and the clock.

Reports conditions only (read-only): the rules are the user's, in playbook.yaml. Nothing here
sizes, places or manages a position; unset fields are shown as "not set", never guessed.
"""
from __future__ import annotations

from datetime import datetime

import yaml

from digest import config
from digest import plain
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
    """What would decide (pre-market) or change (later) the read, in plain words."""
    r, i, lv = b.regime, b.intraday, b.levels
    t = both(c["classify_time_et"])
    cut = both(c["vwap_cutoff_et"])
    n = c["acceptance_closes"]
    if r.label == "undetermined" and b.meta.post_type == "premarket":
        va = f"{plain.PRIOR_VA} ({lv.prior_val}–{lv.prior_vah})" if lv.prior_vah is not None else plain.PRIOR_VA
        if r.lean in ("gap_up", "gap_down"):
            side = "above" if r.lean == "gap_up" else "below"
            return [f"gap-and-go if price is {side} {plain.OR} at {t}", f"gap-and-fill if price is back inside {va} by then"]
        if r.lean in ("open_above_value", "open_below_value"):
            d, side = ("an uptrend", "above") if r.lean == "open_above_value" else ("a downtrend", "below")
            return [f"{d} day if the market opens {side} {va} and stays on that side of its average price (VWAP) until {cut}",
                    f"a range-bound day if it opens back inside {va}"]
        if r.lean == "open_inside_value":
            return [f"a range-bound day if price crosses its average price (VWAP) both ways by {cut}",
                    f"a trend day if the market instead opens outside {va} and holds one side of VWAP"]
        return [f"the classification at {t}"]
    if r.label in ("trend_up", "trend_down") and i.vwap is not None:
        return [f"5-minute closes back {'below' if r.label == 'trend_up' else 'above'} today's average price (VWAP {i.vwap})"]
    if r.label == "gap_and_go":
        return [f"a 5-minute close back inside {plain.OR} ({i.or_low}–{i.or_high})"]
    if r.label == "gap_and_fill":
        up = (lv.gap_pct or 0) > 0
        return [f"price reclaiming the {'top' if up else 'bottom'} of the first 30 minutes ({i.or_high if up else i.or_low})"]
    if r.label == "balance":
        return [f"{plain.closes(n)} outside {plain.DEV_VA} ({i.dev_val}–{i.dev_vah})"]
    return ["the mixed checks under \"What kind of day\" (below) lining up behind one day type"]


def evaluate(b: Brief, rules: dict, pb: dict | None = None) -> Playbook:
    out = _evaluate(b, rules, pb or load_playbook())
    for k in ("early_status", "early_trigger", "early_invalidation", "late_status", "late_trigger", "reasons", "flip"):
        setattr(out, k, tidy(getattr(out, k)))
    return out


SIT_OUT = "not live, option prices are high on a range-bound day (the sit-out combination)"


def _evaluate(b: Brief, rules: dict, pb: dict) -> Playbook:
    sh, early, late = pb["shared"], pb["early"], pb["late"]
    c = rules["classify"]
    r, i, lv, vol = b.regime, b.intraday, b.levels, b.vol
    now = datetime.strptime(b.meta.as_of_pt, "%Y-%m-%d %H:%M").replace(tzinfo=config.PT)
    now_et = _hhmm(now)
    e0, e1 = early["window_et"]
    l0, l1 = late["window_et"]
    n = c["acceptance_closes"]
    out = Playbook(
        live="none", early_window_et=f"{e0}–{e1}", early_time_stop_et=early["time_stop_et"], late_window_et=f"{l0}–{l1}",
        flat_by_et=sh["flat_by_et"], premium_cap=str(late["premium_cap"]) if late.get("premium_cap") is not None else NOT_SET,
        do_not=list(sh.get("never", [])), flip=_flip(b, c),
        instrument=(early["high_iv_instrument"] if vol.iv_high else "single option"),
    )
    if b.meta.market_closed_mode:
        out.early_status = out.late_status = "not live, the market is closed"
        return out
    kinds = [plain.REGIME_PLAIN[x].lower().removesuffix(" day") for x in early["regimes"]]
    wants = ("an " if kinds[0][0] in "aeiou" else "a ") + (", ".join(kinds[:-1]) + " or " + kinds[-1] if len(kinds) > 1 else kinds[0]) + " day"
    today = "today has no clear day type" if r.label == "undetermined" else f"today is a {plain.REGIME_PLAIN[r.label].lower()}"
    if b.meta.post_type == "premarket":
        out.live = "pending"
        out.early_status = f"decided at the {both(c['classify_time_et'])} classification"
        out.early_trigger = (f"if it turns out to be {wants}"
                             + (", and option prices have deflated after the open (or are high)" if early.get("requires_iv_crush") else "")
                             + f": {plain.closes(n)} beyond {plain.OR}, in the day's direction")
        out.late_status = "not live, early close" if b.meta.is_early_close else f"opens {both(l0)}; its trigger is set in the afternoon card"
        out.reasons = [f"no trade until the {both(c['classify_time_et'])} classification"]
        return out

    d = direction(b, r.label) if r.holding is not False else None
    out.direction = d
    sit_out = bool(sh.get("sit_out_high_iv_balance") and vol.iv_high and r.label == "balance")

    # Early playbook.
    if now_et >= e1:
        out.early_status = f"window closed ({both(e1)})"
    elif sit_out:
        out.early_status = SIT_OUT
    elif r.label not in early["regimes"]:
        out.early_status = f"not live, it needs {wants} and {today}"
    elif r.holding is False:
        out.early_status = f"not live, the {plain.REGIME_PLAIN[r.label].lower()} read is no longer holding ({r.holding_note})"
    elif (early.get("requires_iv_crush") and vol.iv_crush_label != "crush done"
          and not (early.get("high_iv_overrides_crush") and vol.iv_high)):
        out.early_status = ("not live, option prices have not deflated enough since the open (IV crush not done)" if vol.iv_crush_label
                            else "not live, no 09:35 ET straddle print to confirm option prices have deflated (IV crush unconfirmed)")
    else:
        up = d == "up"
        edge, name = (i.or_high, "top") if up else (i.or_low, "bottom")
        out.early_status = "live" if now_et >= e0 else f"live from {both(e0)}"
        out.early_trigger = (f"{plain.closes(n)} {'above' if up else 'below'} the {name} of the first 30 minutes ({edge}); "
                             f"price is {i.spot_vs_or} that range now")
        out.early_invalidation = (f"a 5-minute close back inside {plain.OR} ({i.or_low}–{i.or_high})" if r.label == "gap_and_go"
                                  else f"a 5-minute close back {'below' if up else 'above'} today's average price (VWAP {i.vwap})")
    early_live = (out.early_status or "").startswith("live")

    # Late playbook.
    if b.meta.is_early_close:
        out.late_status = "not live, early close"
    elif now_et >= l1:
        out.late_status = f"window closed ({both(l1)})"
    elif sit_out:
        out.late_status = SIT_OUT
    elif lv.spot is None or i.dev_vah is None:
        out.late_status = "not live, today's value area is unavailable"
    else:
        out.late_status = "live" if now_et >= l0 else f"ready, opens {both(l0)}"
        va = f"{plain.DEV_VA} ({i.dev_val}–{i.dev_vah})"
        ratio = rules["premium"]["volume_returning_ratio"]

        def edge_trigger(side: str, note: str = "") -> str:
            edge, word = (i.dev_vah, "top") if side == "above" else (i.dev_val, "bottom")
            return f"{plain.closes(n)} {side} the {word} of {plain.DEV_VA} ({edge}){note}"

        if d:
            side = "above" if d == "up" else "below"
            edge = i.dev_vah if d == "up" else i.dev_val
            lvl = _nearest(b, side)
            use_edge = (edge > lv.spot) if d == "up" else (edge < lv.spot)
            if lvl is not None and not (use_edge and abs(edge - lv.spot) <= abs(lvl.price - lv.spot)):
                stacked = f", where it lines up with {', '.join(plain.level_name(x) for x in lvl.confluence_with.split(', '))}" if lvl.confluence else ""
                out.late_trigger = (f"a break {side} {plain.level_name(lvl.name)} ({lvl.price}){stacked}, on rising volume "
                                    f"(at least {ratio}x the midday average)")
            else:
                out.late_trigger = edge_trigger(side)
        elif i.accepted_outside_dev_va in ("above", "below"):
            out.late_trigger = f"price has already broken out {i.accepted_outside_dev_va} {va}; it counts while 5-minute closes stay outside"
        else:
            up_d, dn_d = i.dev_vah - lv.spot, lv.spot - i.dev_val
            out.late_trigger = edge_trigger("above" if up_d <= dn_d else "below", ", the nearer edge")
    late_on = (out.late_status or "").startswith(("live", "ready"))

    out.live = "early" if early_live else "late" if late_on else "none"
    if early_live:
        out.reasons.append(f"day type {r.label}; IV crush: {vol.iv_crush_label or 'unconfirmed'}"
                           + (f" ({vol.iv_crush_basis})" if vol.iv_crush_basis else ""))
    if vol.iv_high:
        out.reasons.append(f"VIX1D is {vol.vix1d_label} against its last 20 closes: instrument is {early['high_iv_instrument']}" if not sit_out
                           else f"VIX1D is {vol.vix1d_label} on a range-bound day: sit out")
    if r.label == "gap_and_go":
        out.reasons.append("gap-and-go: with-trend only")
    return out
