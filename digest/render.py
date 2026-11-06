"""Post markdown: YAML frontmatter + a quick-reference card rendered by code from the brief.

Claude supplies only the VERDICT line and a short narrative; every number and link on the
card comes from the brief. If the Claude call fails the verdict is the deterministic one.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import yaml

from digest import config
from digest.brief import Brief
from digest.indicators.events import BEA_URL, BLS_URL, EARNINGS_URL, FED_URL
from digest.timefmt import both, num, with_pt

LABEL_ICON = {
    "trend_up": "▲", "trend_down": "▼", "balance": "↔", "gap_and_go": "⏩", "gap_and_fill": "↩", "undetermined": "◌",
    # Labels of schema 1.x posts (kept so the archive still renders).
    "TREND_UP": "▲", "TREND_DOWN": "▼", "RANGE": "↔", "EVENT_WAIT": "⏸", "VOL_EXPANSION": "⚡", "NO_TRADE": "⛔",
}

SECTION_TITLES = {
    "levels": "Levels",
    "vol": "Volatility and premium",
    "positioning": "Positioning (open interest)",
    "cross_asset": "Cross-asset",
    "breadth": "Breadth / leadership",
    "intraday": "Intraday",
    "playbook": "Playbook",
}

MISSED_DAY = "*Missed day? A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.*"
CONCEPTS = [("daily structure", "daily-structure"), ("premium", "premium"), ("volume profile", "volume-profile"), ("edge", "edge"), ("rules", "rules")]
CONCEPT_BASE = "../../concepts/"  # post pages live at posts/<date>/<post>.html

LEAN_TEXT = {
    "gap_up": "gap up (go or fill is decided at the classification)",
    "gap_down": "gap down (go or fill is decided at the classification)",
    "open_above_value": "indicated open above prior value (trend-up candidate)",
    "open_below_value": "indicated open below prior value (trend-down candidate)",
    "open_inside_value": "indicated open inside prior value (balance candidate)",
}


def yq(ticker: str, page: str = "") -> str:
    return f"https://finance.yahoo.com/quote/{quote(ticker)}/{page}"


L = {
    "es": ("ES chart", yq("ES=F", "chart")),
    "spx": ("SPX 5-min", yq("^GSPC", "chart")),
    "spy": ("SPY volume", yq("SPY", "chart")),
    "vix": ("Cboe VIX", "https://www.cboe.com/tradable_products/vix/"),
    "vix1d": ("VIX1D", yq("^VIX1D")),
    "vixcentral": ("vixcentral", "http://vixcentral.com/"),
    "chain": ("Yahoo SPX chain", yq("^SPX", "options")),
    "cboe_quotes": ("Cboe delayed quotes", "https://www.cboe.com/delayed_quotes/spx/quote_table"),
    "sectors": ("sector ETFs", yq("XLK")),
}


def link(key: str) -> str:
    name, url = L[key]
    return f"[{name}]({url})"


def links(*keys: str) -> str:
    return " · ".join(link(k) for k in keys)


def frontmatter(brief: Brief, narrative: str, files: dict, model: str | None, verdict: str | None = None) -> dict:
    return {
        "date": brief.meta.date,
        "post_type": brief.meta.post_type,
        "version": brief.meta.version,
        "regime": brief.regime.label,
        "playbook": brief.playbook.live,
        "verdict": verdict or default_verdict(brief),
        "generated_at": brief.meta.generated_at,
        "data_as_of": brief.meta.data_as_of,
        "schema_version": brief.meta.schema_version,
        "narrative": narrative,  # claude | unavailable | dry-run
        "model": model,
        "files": files,
    }


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v) if v else "—"
    if isinstance(v, dict):
        return ", ".join(f"{k} {fmt(x)}" for k, x in v.items()) if v else "—"
    return str(v)


# --- Verdict -------------------------------------------------------------------------

def verdict_requirements(b: Brief) -> list[str]:
    """Phrases the VERDICT line must contain (checked on Claude's line; the default line has them)."""
    r, p = b.regime, b.playbook
    if b.meta.market_closed_mode:
        return ["market closed"]
    if b.meta.post_type == "premarket":
        return ["10:30 ET / 07:30 PT"]
    if b.meta.post_type == "midsession":
        return [r.label, f"playbook: {p.live}"]
    req = [r.label, "late playbook live" if p.live == "late" else "late playbook not live"]
    if r.confirmation in ("confirmed", "changed"):
        req.append(r.confirmation)
    return req


def default_verdict(b: Brief) -> str:
    r, p = b.regime, b.playbook
    if b.meta.market_closed_mode:
        return "market closed; no session today"
    if b.meta.post_type == "premarket":
        lean = LEAN_TEXT.get(r.lean or "", "no lean (value area or gap unavailable)")
        return f"no trade until the 10:30 ET / 07:30 PT classification; lean: {lean}"
    if b.meta.post_type == "midsession":
        return f"regime classified as {r.label}; playbook: {p.live}"
    state = {"confirmed": f"regime confirmed: {r.label}", "changed": f"regime changed: {r.label} is no longer holding" if r.label == r.prior_label
             else f"regime changed: {r.prior_label} to {r.label}"}.get(r.confirmation or "", f"regime classified as {r.label}")
    return f"{state}; {'late playbook live' if p.live == 'late' else 'late playbook not live'}"


# --- Card fields ------------------------------------------------------------------------

def _events(b: Brief) -> list[str]:
    cal = b.calendar
    out = ["**EVENTS**", ""]
    if cal.events_today:
        for e in cal.events_today:
            src = f" ([source]({e.url}))" if e.url else ""
            out.append(f"- {both(e.time_et)}: {e.name} [{e.premium_relevance}]{src}")
    else:
        out.append(f"- No releases, Fed speakers or mega-cap earnings in the calendars today ([BLS]({BLS_URL}) · [BEA]({BEA_URL}) · [Fed]({FED_URL}))")
    last = ", ".join(cal.earnings_prev_session) if cal.earnings_prev_session else "none listed"
    out.append(f"- Mega-cap earnings last night: {last} ([earnings]({EARNINGS_URL}))")
    return out


def _va(b: Brief) -> str:
    lv = b.levels
    return f"{num(lv.prior_val)}–{num(lv.prior_vah)}" if lv.prior_vah is not None else "n/a"


def _overnight(b: Brief) -> str:
    lv = b.levels
    gap = f"gap {lv.gap_pct:+.2f}% ({lv.gap_pts:+.2f} pts) vs prior close {num(lv.prior_close)}" if lv.gap_pct is not None else "gap n/a"
    where = f"spot {num(lv.spot)} is {lv.spot_vs_prior_va} prior value {_va(b)}" if lv.spot_vs_prior_va else f"spot {num(lv.spot)}; prior value n/a"
    return (f"**OVERNIGHT:** {gap} · O/N high {num(lv.overnight_high)} / low {num(lv.overnight_low)} (ES, in SPX points) · {where} "
            f"— {links('es', 'spx')}")


def _vix1d(b: Brief) -> str:
    v = b.vol
    if v.vix1d is None:
        return "VIX1D n/a"
    if v.vix1d_pctile_20d is None:
        return f"VIX1D {num(v.vix1d)}"
    return f"VIX1D {num(v.vix1d)} ({num(v.vix1d_pctile_20d)}th percentile of its last 20 closes: {v.vix1d_label})"


def _vol(b: Brief) -> str:
    v = b.vol
    term = f"term structure {v.term_structure_label} (VIX/VIX3M {num(v.vix_vix3m_ratio)})" if v.term_structure_label else "term structure n/a"
    return f"**VOL:** VIX {num(v.vix)} · {_vix1d(b)} · {term} — {links('vix', 'vix1d', 'vixcentral')}"


def _straddle(b: Brief) -> str:
    v = b.vol
    if v.expected_move_0dte_pts is None:
        return f"ATM straddle: no free quote for this run (manual input; read it from {links('cboe_quotes', 'chain')})"
    t = f", quoted {both(v.straddle_quote_time_et)}" if v.straddle_quote_time_et else ""
    return (f"ATM straddle {num(v.expected_move_0dte_pts)} at the {num(v.straddle_strike)} strike{t} = ±{num(v.expected_move_0dte_pts)} pts "
            f"({num(v.expected_move_0dte_pct)}% of spot), implied range {num(v.implied_range_low)}–{num(v.implied_range_high)} — {links('chain', 'cboe_quotes')}")


def _stack(b: Brief) -> list[str]:
    lv = b.levels
    out = ["**LEVEL STACK**", ""]
    if not lv.level_stack:
        return out + ["- unavailable"]
    placed = False
    for l in lv.level_stack:
        if not placed and lv.spot is not None and l.price < lv.spot:
            out.append(f"- **▶ spot {num(lv.spot)}**")
            placed = True
        star = f" ★ with {l.confluence_with}" if l.confluence else ""
        out.append(f"- {num(l.price)} {l.name}{star}")
    if not placed and lv.spot is not None:
        out.append(f"- **▶ spot {num(lv.spot)}**")
    out += ["", f"★ marks confluence (levels within {num(_tol())} pts). Value area from prior-day 5-min volume-at-price — {links('spx', 'spy', 'es')}"]
    return out


def _tol() -> float:
    from digest.regime import load_rules

    return float(load_rules()["levels"]["confluence_tolerance_pts"])


def _plan(b: Brief) -> list[str]:
    p = b.playbook
    out = ["**PLAN**", ""]
    out.append(with_pt(f"- Early ({p.early_window_et} ET): {p.early_status}" + (f". Trigger: {p.early_trigger}" if p.early_trigger else "")))
    out.append(with_pt(f"- Late ({p.late_window_et} ET): {p.late_status}"))
    out += [with_pt(f"- Flips the read: {f}") for f in p.flip]
    return out


def _evidence(b: Brief) -> list[str]:
    r, i, br = b.regime, b.intraday, b.breadth
    out = ["**REGIME EVIDENCE**", ""]
    out += [with_pt(f"- {x}") for x in r.rules_fired]
    out += [with_pt(f"- Not met: {x}") for x in r.rules_failed]
    out += [f"- Conflict: {x}" for x in r.conflicts]
    if i.spot_vs_or:
        out.append(f"- ORB: spot {num(b.levels.spot)} is {i.spot_vs_or} the opening range {num(i.or_low)}–{num(i.or_high)}")
    if i.vwap is not None:
        out.append(f"- VWAP {num(i.vwap)}: {num(i.vwap_crosses)} cross(es) so far; spot is {num(abs(i.spot_minus_vwap_pts))} pts "
                   f"{'above' if i.spot_minus_vwap_pts >= 0 else 'below'}")
    if i.profile_shape:
        out.append(f"- Profile so far: {i.profile_shape}-shape, POC {num(i.dev_poc)}, value {num(i.dev_val)}–{num(i.dev_vah)}")
    if br.sectors_up_count is not None:
        out.append(f"- Breadth: {br.sectors_up_count} of {br.sectors_total} sectors up")
    out += ["", f"— {links('spx', 'spy', 'sectors')}"]
    return out


def _crush(b: Brief) -> str:
    v = b.vol
    if v.iv_crush_pct is None:
        return ("**IV CRUSH:** unconfirmed. No 09:35 ET / 06:35 PT straddle print for today (manual input: "
                f"`python -m digest straddle --set PRICE`) — {links('cboe_quotes', 'chain')}")
    state = "done" if v.iv_crush_label == "crush done" else "not done"
    if v.straddle_0935_pts is not None and v.expected_move_0dte_pts is not None:
        return (f"**IV CRUSH:** straddle {num(v.expected_move_0dte_pts)} now vs {num(v.straddle_0935_pts)} at "
                f"{both(v.straddle_0935_time_et or '09:35')} ({v.straddle_0935_source}) = {v.iv_crush_pct:+.2f}%: {state} — {links('chain', 'cboe_quotes')}")
    return with_pt(f"**IV CRUSH:** {v.iv_crush_pct:+.2f}% ({v.iv_crush_basis}): {state} — {links('vix1d', 'cboe_quotes')}")


def _premium(b: Brief) -> str:
    v = b.vol
    theta = (f"{num(v.theta_extrinsic_remaining_pct)}% of ATM extrinsic left ([theta table]({CONCEPT_BASE}premium.html#theta))"
             if v.theta_extrinsic_remaining_pct is not None else "theta n/a")
    return f"**PREMIUM:** {_straddle(b)} · {_vix1d(b)} — {link('vix1d')} · {theta}"


def _in_play(b: Brief) -> list[str]:
    lv = b.levels
    out = ["**LEVELS IN PLAY**", ""]
    if lv.spot is None or not lv.level_stack:
        return out + ["- unavailable"]
    stack = [l for l in lv.level_stack if l.kind != "vwap"]
    for side in ("above", "below"):
        cands = [l for l in stack if (l.price > lv.spot if side == "above" else l.price < lv.spot)]
        if not cands:
            out.append(f"- {side.capitalize()}: no level in the stack")
            continue
        conf = [l for l in cands if l.confluence]
        l = min(conf or cands, key=lambda x: abs(x.price - lv.spot))
        beyond = [x for x in cands if (x.price > l.price + _tol() if side == "above" else x.price < l.price - _tol())]
        nxt = min(beyond, key=lambda x: abs(x.price - l.price)) if beyond else None
        tag = f" ★ with {l.confluence_with}" if l.confluence else " (no confluence nearby; nearest level)"
        means = f"acceptance {side} it opens {num(nxt.price)} {nxt.name}" if nxt else f"acceptance {side} it leaves the level stack"
        out.append(f"- {side.capitalize()}: {num(l.price)} {l.name}{tag}: {means}")
    out += ["", f"— {links('spx', 'spy')}"]
    return out


def _early(b: Brief) -> str:
    p = b.playbook
    s = f"**EARLY PLAYBOOK:** {p.early_status}"
    if p.early_trigger:
        s += (f" · trigger: {p.early_trigger} · invalidation: {p.early_invalidation} · time stop {p.early_time_stop_et} ET"
              f" · instrument: {p.instrument}")
    if p.live == "late":
        s += f"\n\n**LATE PLAYBOOK:** {p.late_status}"
    return with_pt(s)


def _range(b: Brief) -> str:
    lv, i = b.levels, b.intraday
    dev = f"developing value {num(i.dev_val)}–{num(i.dev_vah)} (POC {num(i.dev_poc)})" if i.dev_vah is not None else "developing value n/a"
    return (f"**RANGE SO FAR:** high {num(lv.session_high)} / low {num(lv.session_low)} · spot {num(lv.spot)} at "
            f"{num(lv.range_position_pct)}% of the range · {dev} · prior value {_va(b)} — {links('spx', 'spy')}")


def _late(b: Brief) -> str:
    p = b.playbook
    s = f"**LATE TRIGGER:** {p.late_status}"
    if p.late_trigger:
        s += f" · {p.late_trigger}"
    s += f" · premium cap: {p.premium_cap} · flat by {p.flat_by_et} ET"
    return with_pt(s)


def _theta(b: Brief) -> str:
    now_et = datetime.strptime(b.meta.as_of_pt, "%Y-%m-%d %H:%M").replace(tzinfo=config.PT).astimezone(config.ET).strftime("%H:%M")
    return (f"**THETA NOW:** {num(b.vol.theta_extrinsic_remaining_pct)}% of ATM extrinsic remaining at {both(now_et)} "
            f"(sqrt-of-time model, [theta table]({CONCEPT_BASE}premium.html#theta))")


def _sources(b: Brief) -> list[str]:
    out = ["**Sources**", ""]
    for s in b.data_quality.sources:
        when = ""
        if s.fetched_at_utc:
            t = datetime.fromisoformat(s.fetched_at_utc).astimezone(config.ET).strftime("%H:%M")
            when = f", fetched {both(t)}"
        out.append(f"- [{s.name}]({s.url}){when}{'' if s.ok else ' (failed this run)'}")
    gex = f"[vendor]({b.positioning.gex_vendor_url})" if b.positioning.gex_vendor_url else "vendor link not set"
    out.append(f"- Dealer gamma / GEX: not computed or estimated ({gex})")
    out += ["", "Concepts: " + " · ".join(f"[{n}]({CONCEPT_BASE}{slug}.html)" for n, slug in CONCEPTS)]
    return out


def card(b: Brief, verdict: str | None = None, narrative: str | None = None) -> str:
    """The whole post body."""
    blocks: list[str] = [f"**VERDICT:** {verdict or default_verdict(b)}"]
    pt = b.meta.post_type
    if b.meta.market_closed_mode:
        blocks += ["\n".join(_events(b)), _vol(b)]
    elif pt == "premarket":
        blocks += ["\n".join(_events(b)), _overnight(b), _vol(b), f"**EXPECTED MOVE:** {_straddle(b)}", "\n".join(_stack(b)), "\n".join(_plan(b))]
    elif pt == "midsession":
        blocks += ["\n".join(_evidence(b)), _crush(b), _premium(b), "\n".join(_in_play(b)), _early(b)]
    else:
        blocks += [_range(b), _late(b), _theta(b), _premium(b),
                   with_pt("**DO NOT:** " + " · ".join(b.playbook.do_not))]
    if narrative:
        blocks.append(narrative.strip())
    if b.data_quality.manual_inputs:
        blocks.append("\n".join(["**Manual inputs open**", ""] + [with_pt(f"- {m}") for m in b.data_quality.manual_inputs]))
    blocks += [MISSED_DAY, "\n".join(_sources(b))]
    return "\n\n".join(blocks) + "\n"


def unavailable_body(b: Brief) -> str:
    """Claude call failed: same card with the deterministic verdict and no narrative."""
    return "**Narrative unavailable: showing the computed card.**\n\n" + card(b)


def post_markdown(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def split_post(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")
