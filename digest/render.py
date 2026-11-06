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
        "watch": watch(brief),
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


# --- Card pieces ------------------------------------------------------------------------

def _tol() -> float:
    from digest.regime import load_rules

    return float(load_rules()["levels"]["confluence_tolerance_pts"])


def _va(b: Brief) -> str:
    lv = b.levels
    return f"{num(lv.prior_val)}–{num(lv.prior_vah)}" if lv.prior_vah is not None else "n/a"


def clusters(b: Brief) -> list[dict]:
    """The level stack, high to low, with neighbours inside the confluence tolerance merged into one line."""
    tol, out = _tol(), []
    for l in b.levels.level_stack:
        if out and out[-1]["lo"] - l.price <= tol:
            out[-1]["lo"] = l.price
            out[-1]["names"].append(l.name)
        else:
            out.append({"hi": l.price, "lo": l.price, "names": [l.name]})
    return out


def _cl(c: dict) -> str:
    px = num(c["hi"]) if c["hi"] == c["lo"] else f"{num(c['lo'])}–{num(c['hi'])}"
    names = ["round" if n.startswith("round ") else n for n in c["names"]]
    return f"{px} {'★ ' if len(names) > 1 else ''}{' · '.join(names)}"


def _around(b: Brief):
    """(clusters above spot nearest first, clusters below spot nearest first)."""
    s, cs = b.levels.spot, clusters(b)
    if s is None:
        return [], []
    return [c for c in reversed(cs) if c["lo"] > s], [c for c in cs if c["hi"] < s]


def _level_lines(b: Brief, limit: int | None) -> list[str]:
    above, below = _around(b)
    s = b.levels.spot
    at = [c for c in clusters(b) if s is not None and c["lo"] <= s <= c["hi"]]
    if limit:
        above, below = above[:limit], below[:limit]
    out = [f"- {_cl(c)}" for c in reversed(above)]
    out.append(f"- **▶ spot {num(s)}**" + (f" (at {_cl(at[0])})" if at else ""))
    out += [f"- {_cl(c)}" for c in below]
    return out


def _watch_levels(b: Brief) -> list[str]:
    """Nearest level each side (a confluence cluster when one is close) and what sits beyond it."""
    out = []
    for arrow, side, cs in (("▲", "above", _around(b)[0]), ("▼", "below", _around(b)[1])):
        if not cs:
            continue
        i = next((k for k, c in enumerate(cs[:3]) if len(c["names"]) > 1), 0)
        nxt = f"; {side} it, next is {_cl(cs[i + 1])}" if i + 1 < len(cs) else ""
        out.append(f"{arrow} {_cl(cs[i])}{nxt}")
    return out


def _vix1d(b: Brief) -> str:
    v = b.vol
    if v.vix1d is None:
        return "VIX1D n/a"
    if v.vix1d_pctile_20d is None:
        return f"VIX1D {num(v.vix1d)}"
    return f"VIX1D {num(v.vix1d)} ({v.vix1d_label}, {num(v.vix1d_pctile_20d)}th pct of 20 closes)"


def _crush_text(b: Brief) -> str:
    v = b.vol
    if v.iv_crush_pct is None:
        return "IV crush unconfirmed (no 09:35 ET print)"
    est = "" if v.straddle_0935_pts is not None else " (VIX1D estimate)"
    return f"IV crush {v.iv_crush_pct:+.1f}%{est}: {'done' if v.iv_crush_label == 'crush done' else 'not done, needs -20%'}"


def _em_text(b: Brief) -> str | None:
    v = b.vol
    if v.expected_move_0dte_pts is None:
        return None
    return f"±{num(v.expected_move_0dte_pts)} ({num(v.expected_move_0dte_pct)}%) → {num(v.implied_range_low)}–{num(v.implied_range_high)}"


def watch(b: Brief) -> list[str]:
    """Verdict summary: the few levels, indicators and triggers that would flag an opportunity. Plain text."""
    p, r, lv, v = b.playbook, b.regime, b.levels, b.vol
    out: list[str] = []
    if b.meta.market_closed_mode:
        return out
    if b.meta.post_type == "premarket":
        if lv.gap_pct is not None:
            where = f", spot {num(lv.spot)} {lv.spot_vs_prior_va} prior value {_va(b)}" if lv.spot_vs_prior_va else ""
            out.append(f"Gap {lv.gap_pct:+.2f}%{where}")
        if _em_text(b):
            out.append(f"Expected move {_em_text(b)}")
        out += _watch_levels(b)
        out.append(_vix1d(b))
        key = [e for e in b.calendar.events_today if e.premium_relevance in ("high", "medium") and e.time_et][:3]
        if key:
            out.append("Catalysts: " + "; ".join(f"{both(e.time_et)} {e.name}" for e in key))
        out.append("Decides it: " + "; ".join(p.flip))
    elif b.meta.post_type == "midsession":
        if p.early_trigger:
            out.append(f"Early trigger: {p.early_trigger}. Invalidation: {p.early_invalidation}. Time stop {p.early_time_stop_et} ET. Instrument: {p.instrument}")
        else:
            out.append(f"Early: {p.early_status}")
        if p.live == "late":
            out.append(f"Late: {p.late_status}")
        out += _watch_levels(b)
        out.append(f"{_crush_text(b)} · {_vix1d(b)}")
        out.append("Flips the read: " + "; ".join(p.flip))
    else:
        out.append(f"Late: {p.late_status}" + (f". Trigger: {p.late_trigger}" if p.late_trigger else ""))
        out += _watch_levels(b)
        out.append(f"{num(v.theta_extrinsic_remaining_pct)}% of ATM extrinsic left · premium cap: {p.premium_cap} · flat by {p.flat_by_et} ET")
        if r.holding_note:
            out.append(f"Regime {'holding' if r.holding else 'not holding'}: {r.holding_note}")
    return [with_pt(x) for x in out]


# --- Technical ----------------------------------------------------------------------------

def _regime_block(b: Brief) -> str:
    r = b.regime
    state = {"confirmed": ", confirmed", "changed": ", changed"}.get(r.confirmation or "", "")
    out = [f"**Regime: {r.label}{state}** — {links('spx', 'spy')}", ""]
    for x in r.rules_fired:
        note = x.startswith(("provisional", "no rule set", "before the", "market closed", "data missing"))
        out.append(with_pt(f"- {'◷' if note else '✓'} {x.split(': ', 1)[-1] if x.split(': ', 1)[0] == r.label else x}"))
    out += [with_pt(f"- ✗ {x}") for x in r.rules_failed]
    out += [f"- ⚠ {x}" for x in r.conflicts]
    if r.holding_note:
        out.append(f"- Now: {r.holding_note} ({'holding' if r.holding else 'not holding'})")
    return "\n".join(out)


def _structure(b: Brief) -> str:
    i, lv, br = b.intraday, b.levels, b.breadth
    parts = []
    if i.spot_vs_or:
        parts.append(f"spot {num(lv.spot)} {i.spot_vs_or} the opening range {num(i.or_low)}–{num(i.or_high)}")
    if i.vwap is not None:
        parts.append(f"VWAP {num(i.vwap)} ({num(i.vwap_crosses)} crosses, spot {i.spot_minus_vwap_pts:+.2f})")
    if i.profile_shape:
        parts.append(f"{i.profile_shape}-profile, POC {num(i.dev_poc)}, value {num(i.dev_val)}–{num(i.dev_vah)}")
    if lv.session_high is not None:
        parts.append(f"range {num(lv.session_low)}–{num(lv.session_high)}, spot at {num(lv.range_position_pct)}%")
    if br.sectors_up_count is not None:
        parts.append(f"{br.sectors_up_count}/{br.sectors_total} sectors up")
    return f"**Structure:** {' · '.join(parts)} — {links('spx', 'spy', 'sectors')}"


def _overnight(b: Brief) -> str:
    lv = b.levels
    gap = f"gap {lv.gap_pct:+.2f}% ({lv.gap_pts:+.2f}) vs close {num(lv.prior_close)}" if lv.gap_pct is not None else "gap n/a"
    where = f"spot {num(lv.spot)} {lv.spot_vs_prior_va} prior value {_va(b)}" if lv.spot_vs_prior_va else f"spot {num(lv.spot)}"
    return f"**Overnight:** {gap} · O/N {num(lv.overnight_low)}–{num(lv.overnight_high)} · {where} — {links('es', 'spx')}"


def _vol(b: Brief) -> str:
    v = b.vol
    term = f"{v.term_structure_label} (VIX/VIX3M {num(v.vix_vix3m_ratio)})" if v.term_structure_label else "term structure n/a"
    return f"**Vol:** VIX {num(v.vix)} · {_vix1d(b)} · {term} — {links('vix', 'vix1d', 'vixcentral')}"


def _premium(b: Brief) -> str:
    v = b.vol
    parts = []
    if v.expected_move_0dte_pts is None:
        parts.append("straddle: no free quote this run")
    else:
        t = f", {both(v.straddle_quote_time_et)}" if v.straddle_quote_time_et else ""
        parts.append(f"straddle {num(v.expected_move_0dte_pts)} @ {num(v.straddle_strike)}{t} = {_em_text(b)}")
    if b.meta.post_type != "premarket":
        if v.straddle_0935_pts is not None:
            parts.append(f"{_crush_text(b)} vs {num(v.straddle_0935_pts)} at {both(v.straddle_0935_time_et or '09:35')} ({v.straddle_0935_source})")
        else:
            parts.append(_crush_text(b))
    if v.theta_extrinsic_remaining_pct is not None and b.meta.post_type != "premarket":
        parts.append(f"{num(v.theta_extrinsic_remaining_pct)}% of ATM extrinsic left ([theta table]({CONCEPT_BASE}premium.html#theta))")
    label = "Expected move" if b.meta.post_type == "premarket" else "Premium"
    return with_pt(f"**{label}:** {' · '.join(parts)} — {links('chain', 'cboe_quotes')}")


def _levels(b: Brief, limit: int | None) -> str:
    if not b.levels.level_stack:
        return "**Levels:** unavailable"
    return "\n".join([f"**Levels** (★ = within {num(_tol())} pts of each other) — {links('spx', 'spy', 'es')}", ""] + _level_lines(b, limit))


def _playbook(b: Brief) -> str:
    """Status of each playbook. Triggers are in the Verdict section, not repeated here."""
    p = b.playbook
    out = [f"**Playbook: {p.live}**", ""]
    early = f"- Early ({p.early_window_et} ET): {p.early_status}"
    if p.early_trigger and b.meta.post_type == "premarket":
        early += f". Trigger {p.early_trigger}"
    out += [early, f"- Late ({p.late_window_et} ET): {p.late_status}"]
    if b.meta.post_type == "afternoon":
        out.append("- Do not: " + " · ".join(p.do_not))
    return with_pt("\n".join(out))


# --- News / macro ------------------------------------------------------------------------------

def _news(b: Brief) -> str:
    cal, xa = b.calendar, b.cross_asset
    out = []
    now_et = datetime.strptime(b.meta.as_of_pt, "%Y-%m-%d %H:%M").replace(tzinfo=config.PT).astimezone(config.ET).strftime("%H:%M")
    for e in cal.events_today:
        done = " (out)" if e.time_et and e.time_et <= now_et and b.meta.post_type != "premarket" else ""
        src = f" ([source]({e.url}))" if e.url else ""
        out.append(f"- {both(e.time_et)} · {e.name} · {e.premium_relevance}{done}{src}")
    if not cal.events_today:
        out.append(f"- Nothing scheduled today in the calendars ([BLS]({BLS_URL}) · [BEA]({BEA_URL}) · [Fed]({FED_URL}))")
    if b.meta.post_type == "premarket" or cal.earnings_prev_session:
        out.append(f"- Mega-cap earnings last night: {', '.join(cal.earnings_prev_session) or 'none listed'} ([earnings]({EARNINGS_URL}))")
    macro = []
    if xa.us10y_yield_pct is not None:
        macro.append(f"10y {num(xa.us10y_yield_pct)}%" + (f" ({xa.us10y_change_bp:+.1f} bp)" if xa.us10y_change_bp is not None else ""))
    for name, lvl, ch in (("DXY", xa.dxy, xa.dxy_change_pct), ("oil", xa.oil, xa.oil_change_pct), ("gold", xa.gold, xa.gold_change_pct)):
        if lvl is not None:
            macro.append(f"{name} {num(lvl)}" + (f" ({ch:+.2f}%)" if ch is not None else ""))
    if macro:
        out.append(f"- {' · '.join(macro)} — [Yahoo]({yq('^TNX')})")
    for h in cal.headlines[:3]:
        out.append(f"- {h.title} ({h.source})")
    return "\n".join(out)


def _sources(b: Brief) -> str:
    src = b.data_quality.sources
    times = sorted(datetime.fromisoformat(s.fetched_at_utc).astimezone(config.ET).strftime("%H:%M") for s in src if s.fetched_at_utc)
    when = ""
    if times:
        when = f" (fetched {both(times[0])})" if times[0] == times[-1] else with_pt(f" (fetched {times[0]}–{times[-1]} ET)")
    items = " · ".join(f"[{s.name}]({s.url}){'' if s.ok else ' (failed)'}" for s in src)
    gex = f"[vendor]({b.positioning.gex_vendor_url})" if b.positioning.gex_vendor_url else "vendor link not set"
    return (f"**Sources**{when}: {items}\n\nDealer gamma / GEX: not computed or estimated ({gex}). "
            "Concepts: " + " · ".join(f"[{n}]({CONCEPT_BASE}{slug}.html)" for n, slug in CONCEPTS))


NARRATIVE_UNAVAILABLE = "*Narrative unavailable: this is the computed verdict.*"


def card(b: Brief, verdict: str | None = None, narrative: str | None = None) -> str:
    """The whole post body: Verdict (with the watch list), Technical, News / macro, sources."""
    blocks: list[str] = ["## Verdict", f"**{verdict or default_verdict(b)}**"]
    w = watch(b)
    if w:
        blocks.append("\n".join(f"- {x}" for x in w))
    if narrative:
        blocks.append(narrative.strip())
    pt = b.meta.post_type
    blocks.append("## Technical")
    if b.meta.market_closed_mode:
        blocks.append(_vol(b))
    elif pt == "premarket":
        blocks += [_overnight(b), _vol(b), _premium(b), _levels(b, None), _playbook(b)]
    else:
        blocks += [_regime_block(b), _structure(b), _premium(b), _levels(b, 3), _playbook(b)]
    blocks += ["## News / macro", _news(b)]
    if b.data_quality.manual_inputs:
        blocks.append("**Manual inputs open:** " + with_pt("; ".join(b.data_quality.manual_inputs)))
    blocks += [MISSED_DAY, _sources(b)]
    return "\n\n".join(blocks) + "\n"


def unavailable_body(b: Brief) -> str:
    """Claude call failed: same card with the computed verdict and a one-line note in place of the narrative."""
    return card(b, None, NARRATIVE_UNAVAILABLE)


def post_markdown(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def split_post(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")
