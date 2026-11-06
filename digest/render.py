"""Post markdown: YAML frontmatter + a quick-reference card rendered by code from the brief.

Claude supplies only the VERDICT line and a short narrative; every number and link on the
card comes from the brief. If the Claude call fails the verdict is the deterministic one.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import yaml

from digest import config, plain
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
        "meaning": (meaning(brief) or "").strip("*") or None,
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
    name = plain.REGIME_PLAIN[r.label]
    if b.meta.market_closed_mode:
        return "market closed; no session today"
    if b.meta.post_type == "premarket":
        lean = plain.LEAN_PLAIN.get(r.lean or "", "none yet (yesterday's value area or the gap is unavailable)")
        return f"No trade until the day type is set at 10:30 ET / 07:30 PT. Early lean: {lean}"
    if b.meta.post_type == "midsession":
        return f"{name} ({r.label}); playbook: {p.live}"
    late = "late playbook live" if p.live == "late" else "late playbook not live"
    if r.confirmation == "confirmed":
        return f"{name} confirmed ({r.label}); {late}"
    if r.confirmation == "changed":
        was = (f"the {name.lower()} read ({r.label}) is no longer holding" if r.label == r.prior_label
               else f"this morning's read was {r.prior_label}, now {name.lower()} ({r.label})")
        return f"The read has changed: {was}; {late}"
    return f"{name} ({r.label}); {late}"


def meaning(b: Brief) -> str | None:
    """One sentence under the verdict saying what the day type means."""
    if b.meta.market_closed_mode:
        return None
    if b.meta.post_type == "premarket":
        return ("*How to read this: the first hour sets the tone. At 10:30 ET / 07:30 PT the day type is read from where price sits "
                "against the first 30 minutes' range and against yesterday's value area (the price zone where most of yesterday's trading happened).*")
    return f"*In plain terms: {plain.REGIME_MEANS[b.regime.label]}*"


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


def _px(c: dict) -> str:
    return num(c["hi"]) if c["hi"] == c["lo"] else f"{num(c['lo'])}–{num(c['hi'])}"


def _names(c: dict) -> str:
    seen = []
    for n in c["names"]:
        n = plain.level_name(n)
        if n not in seen:
            seen.append(n)
    return " + ".join(seen)


def _cl(c: dict) -> str:
    return f"{_px(c)} {'★ ' if len(c['names']) > 1 else ''}{_names(c)}"


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
    out.append(f"- **▶ price now {num(s)}**" + (f" (sitting at {_cl(at[0])})" if at else ""))
    out += [f"- {_cl(c)}" for c in below]
    return out


def _watch_levels(b: Brief) -> list[str]:
    """The nearest level each side (a stacked one when it is close) and what lies beyond it."""
    out = []
    for word, side, cs in (("Ceiling", "above", _around(b)[0]), ("Floor", "below", _around(b)[1])):
        if not cs:
            continue
        i = next((k for k, c in enumerate(cs[:3]) if len(c["names"]) > 1), 0)
        c = cs[i]
        stacked = " Several levels meet here, which makes it stronger." if len(c["names"]) > 1 else ""
        nxt = f" If price holds {side} it, the next level is {_px(cs[i + 1])} ({_names(cs[i + 1])})." if i + 1 < len(cs) else ""
        out.append(f"{word}: {_px(c)} ({_names(c)}).{stacked}{nxt}")
    return out


def _vix1d(b: Brief) -> str:
    """VIX1D in words: what it is, how it compares, and what that means for option prices."""
    v = b.vol
    if v.vix1d is None:
        return "the 1-day volatility gauge (VIX1D) is unavailable"
    if v.vix1d_pctile_20d is None:
        return f"the 1-day volatility gauge (VIX1D) is {num(v.vix1d)}"
    so = {"low": "so options are cheaper than usual", "normal": "so options are priced about as usual",
          "high": "so options cost more than usual", "extreme": "so options are very expensive"}[v.vix1d_label]
    rank = {0: "lower than every one", 100: "higher than every one"}.get(round(v.vix1d_pctile_20d), f"higher than {num(v.vix1d_pctile_20d)}%")
    return f"the 1-day volatility gauge (VIX1D) is {num(v.vix1d)}, {rank} of the last 20 days, {so}"


def _crush_text(b: Brief) -> str:
    """Option prices normally deflate after the open (the IV crush); say how far that has gone."""
    v = b.vol
    if v.iv_crush_pct is None:
        return ("there is no 09:35 ET straddle print today, so the card cannot say whether option prices have deflated since the open "
                "(the IV crush)")
    est = " (an estimate from VIX1D, since there is no 09:35 ET print)" if v.straddle_0935_pts is None else ""
    crush = "the usual deflation once the open is out of the way (the IV crush)"
    if v.iv_crush_pct >= 0:
        return f"option prices have risen {num(v.iv_crush_pct)}% since the open{est}, the opposite of {crush}"
    if v.iv_crush_label == "crush done":
        return f"option prices have deflated {num(abs(v.iv_crush_pct))}% since the open{est}, past the 20% mark where {crush} is treated as finished"
    return (f"option prices have deflated {num(abs(v.iv_crush_pct))}% since the open{est}. The early setup waits for 20%, "
            f"the mark where {crush} is treated as finished")


def _em_text(b: Brief) -> str | None:
    v = b.vol
    if v.expected_move_0dte_pts is None:
        return None
    return (f"about ±{num(v.expected_move_0dte_pts)} points for the rest of today ({num(v.expected_move_0dte_pct)}%), "
            f"a range of {num(v.implied_range_low)}–{num(v.implied_range_high)}")


def _cap(x: str) -> str:
    return x[:1].upper() + x[1:]


def watch(b: Brief) -> list[str]:
    """Verdict summary: the few levels and conditions worth watching, each with why it matters. Plain text."""
    p, r, lv, v = b.playbook, b.regime, b.levels, b.vol
    out: list[str] = []
    if b.meta.market_closed_mode:
        return out
    if b.meta.post_type == "premarket":
        if lv.gap_pct is not None:
            where = f", {lv.spot_vs_prior_va} {plain.PRIOR_VA} ({_va(b)})" if lv.spot_vs_prior_va else ""
            big = abs(lv.gap_pct) > 0.5
            so = ("That is a real gap: the first hour decides whether it keeps going or fills." if big
                  else "That is not a gap worth trading on its own.")
            out.append(f"The open: futures point to {num(lv.spot)}, {lv.gap_pct:+.2f}% from yesterday's close{where}. {so}")
        if _em_text(b):
            out.append(f"Expected move: options are pricing {_em_text(b)}. A move past either end is a bigger day than the market expects.")
        out += _watch_levels(b)
        out.append(f"Option prices: {_vix1d(b)}.")
        key = [e for e in b.calendar.events_today if e.premium_relevance in ("high", "medium") and e.time_et][:3]
        if key:
            out.append("Scheduled news that can move the market: " + "; ".join(f"{both(e.time_et)} {_event_name(e)}" for e in key) + ".")
        out.append("What decides the day type: " + "; ".join(p.flip) + ".")
    elif b.meta.post_type == "midsession":
        if p.early_trigger:
            spread = " (buy one option and sell a further-out one against it, which lowers the cost when options are expensive)" if p.instrument == "debit spread" else ""
            out.append(f"Early setup is live. Trigger: {p.early_trigger}. It is off on {p.early_invalidation}. "
                       f"Out by {p.early_time_stop_et} ET either way. Instrument: {p.instrument}{spread}.")
        else:
            out.append(f"Early setup: {p.early_status}.")
        if p.live == "late":
            out.append(f"Late setup: {p.late_status}.")
        out += _watch_levels(b)
        out.append(f"{_cap(_crush_text(b))}. Also, {_vix1d(b)}.")
        out.append("What would change this read: " + "; ".join(p.flip) + ".")
    else:
        out.append(f"Late setup ({p.late_window_et} ET): {p.late_status}." + (f" Trigger: {p.late_trigger}." if p.late_trigger else ""))
        out += _watch_levels(b)
        out.append(f"Time is the cost now: about {num(v.theta_extrinsic_remaining_pct)}% of an at-the-money option's time value is left, "
                   f"and it melts faster every minute from here. Premium cap: {p.premium_cap}. Be flat by {p.flat_by_et} ET.")
        if r.holding_note:
            out.append(f"The {plain.REGIME_PLAIN[r.label].lower()} read is {'still holding' if r.holding else 'no longer holding'}: {r.holding_note}.")
    return [with_pt(x) for x in out]


# --- Technical ----------------------------------------------------------------------------

def _regime_block(b: Brief) -> str:
    r = b.regime
    state = {"confirmed": ", confirmed this afternoon", "changed": ", changed since this morning"}.get(r.confirmation or "", "")
    out = [f"**What kind of day: {plain.REGIME_PLAIN[r.label]} ({r.label}){state}** — {links('spx', 'spy')}", "",
           "The checks behind that call (✓ met, ✗ not met):", ""]
    for x in r.rules_fired:
        note = x.startswith(("provisional", "no rule set", "before the", "market closed", "data missing"))
        out.append(with_pt(f"- {'◷' if note else '✓'} {_cap(x.split(': ', 1)[-1]) if x.split(': ', 1)[0] in plain.REGIME_PLAIN else _cap(x)}"))
    for x in r.rules_failed:
        head, _, rest = x.partition(": ")
        label = plain.REGIME_PLAIN.get(head, "Gap day" if head == "gap rules" else head)
        out.append(with_pt(f"- ✗ {label}: {rest}"))
    out += [f"- ⚠ {x}" for x in r.conflicts]
    return "\n".join(out)


def _now(b: Brief) -> str:
    """Where price is now, in three plain facts: versus today's average, versus the first 30 minutes, and breadth."""
    i, lv, br = b.intraday, b.levels, b.breadth
    parts = [f"{num(lv.spot)}"]
    if i.vwap is not None and i.spot_minus_vwap_pts is not None:
        side = "above" if i.spot_minus_vwap_pts >= 0 else "below"
        who = "buyers" if side == "above" else "sellers"
        parts.append(f"That is {num(abs(i.spot_minus_vwap_pts))} points {side} today's average price (VWAP {num(i.vwap)}), so {who} have the upper hand right now")
    if i.spot_vs_or:
        what = {"inside": "no breakout in either direction", "above": "an upside breakout", "below": "a downside breakout"}[i.spot_vs_or]
        parts.append(f"It is {i.spot_vs_or} {plain.OR} ({num(i.or_low)}–{num(i.or_high)}): {what}")
    if br.sectors_up_count is not None and br.sectors_total:
        n, t = br.sectors_up_count, br.sectors_total
        breadth = "the buying is broad" if n >= 8 else "the selling is broad" if n <= 3 else "the market is mixed underneath"
        parts.append(f"{n} of {t} sectors are up, so {breadth}")
    return f"**Where price is now:** {'. '.join(parts)}. — {links('spx', 'spy', 'sectors')}"


def _overnight(b: Brief) -> str:
    lv = b.levels
    gap = (f"Futures point to an open near {num(lv.spot)}, {lv.gap_pct:+.2f}% ({lv.gap_pts:+.2f} points) from yesterday's close of {num(lv.prior_close)}"
           if lv.gap_pct is not None else f"Indicated open {num(lv.spot)}")
    where = f". That is {lv.spot_vs_prior_va} {plain.PRIOR_VA} ({_va(b)})" if lv.spot_vs_prior_va else ""
    rng = f". Overnight, futures traded between {num(lv.overnight_low)} and {num(lv.overnight_high)} (in index points)" if lv.overnight_high is not None else ""
    return f"**Overnight:** {gap}{where}{rng}. — {links('es', 'spx')}"


TERM_PLAIN = {
    "contango": "Near-term volatility is below longer-term volatility, which is the normal, calm state.",
    "backwardation": "Near-term volatility is above longer-term volatility, which is a sign of stress.",
    "flat": "Near-term and longer-term volatility are about equal.",
}


def _vol(b: Brief) -> str:
    v = b.vol
    term = f" {TERM_PLAIN[v.term_structure_label]}" if v.term_structure_label else ""
    return (f"**Volatility:** VIX, the market's 30-day fear gauge, is {num(v.vix)}. For today alone, {_vix1d(b)}.{term} "
            f"— {links('vix', 'vix1d', 'vixcentral')}")


def _premium(b: Brief) -> str:
    v = b.vol
    parts = []
    if v.expected_move_0dte_pts is None:
        parts.append("No free straddle quote was available for this run, so today's expected move is not shown")
    else:
        t = f" (quote from {both(v.straddle_quote_time_et)})" if v.straddle_quote_time_et else ""
        parts.append(f"An at-the-money straddle (a call plus a put at the current price) costs {num(v.expected_move_0dte_pts)} points{t}. "
                     f"That is the move options are pricing: {_em_text(b)}")
    if b.meta.post_type != "premarket":
        ref = (f" The 09:35 ET print was {num(v.straddle_0935_pts)} ({v.straddle_0935_source})" if v.straddle_0935_pts is not None else "")
        parts.append(_cap(_crush_text(b)) + "." + ref)
        if v.theta_extrinsic_remaining_pct is not None:
            parts.append(f"About {num(v.theta_extrinsic_remaining_pct)}% of an at-the-money option's time value is left today "
                         f"([how it melts through the day]({CONCEPT_BASE}premium.html#theta))")
    label = "What options are pricing" if b.meta.post_type == "premarket" else "Option prices"
    text = ". ".join(x.rstrip(".") for x in parts)
    return with_pt(f"**{label}:** {text}. — {links('chain', 'cboe_quotes')}")


def _levels(b: Brief, limit: int | None) -> str:
    if not b.levels.level_stack:
        return "**Key levels:** unavailable"
    head = (f"**Key levels** — {links('spx', 'spy', 'es')}\n\n"
            f"Prices where the market has turned or traded heavily. ★ marks several within {num(_tol())} points of each other, "
            "which tends to make that area matter more. A value area is the zone that held about 70% of a day's trading.\n")
    return "\n".join([head] + _level_lines(b, limit))


def _playbook(b: Brief) -> str:
    """Status of each playbook. Triggers are in the Verdict section, not repeated here."""
    p = b.playbook
    title = {"early": "the early one is live", "late": "the late one is live", "none": "neither is live", "pending": "decided at 10:30 ET"}[p.live]
    out = [f"**Your playbooks: {title}**", ""]
    early = f"- Early ({p.early_window_et} ET): {p.early_status}"
    if p.early_trigger and b.meta.post_type == "premarket":
        early += f". It would trigger {p.early_trigger}"
    out += [early, f"- Late ({p.late_window_et} ET): {p.late_status}"]
    if b.meta.post_type == "afternoon":
        out.append("- Do not: " + " · ".join(p.do_not))
    return with_pt("\n".join(out))


# --- News / macro ------------------------------------------------------------------------------

BIG_MOVE = {"us10y_bp": 5.0, "dxy_pct": 0.5, "oil_pct": 2.0, "gold_pct": 1.5}
FED_HEADLINE_WORDS = ("fomc", "federal funds", "monetary policy", "interest rate", "statement")


def _event_name(e) -> str:
    if e.category in plain.EVENT_PLAIN:
        return plain.EVENT_PLAIN[e.category]
    name = e.name.replace("UoM", "University of Michigan").replace("Prelim ", "Preliminary ")
    if e.category in ("FED_SPEAKER", "FED_TESTIMONY"):
        return f"Fed speaker: {name}"
    return name


def _other_markets(b: Brief) -> str | None:
    """Only large moves in rates, the dollar, oil or gold: the ones that tend to spill into stocks."""
    xa = b.cross_asset
    moves = []
    if xa.us10y_change_bp is not None and abs(xa.us10y_change_bp) >= BIG_MOVE["us10y_bp"]:
        moves.append(f"the 10-year Treasury yield is {'up' if xa.us10y_change_bp > 0 else 'down'} {num(abs(xa.us10y_change_bp))} basis points to {num(xa.us10y_yield_pct)}%")
    for name, lvl, ch, thr in (("the dollar index", xa.dxy, xa.dxy_change_pct, BIG_MOVE["dxy_pct"]), ("oil", xa.oil, xa.oil_change_pct, BIG_MOVE["oil_pct"]),
                               ("gold", xa.gold, xa.gold_change_pct, BIG_MOVE["gold_pct"])):
        if ch is not None and lvl is not None and abs(ch) >= thr:
            moves.append(f"{name} is {'up' if ch > 0 else 'down'} {num(abs(ch))}% at {num(lvl)}")
    if not moves:
        return None
    return f"- Big moves elsewhere, which often spill into stocks: {'; '.join(moves)} ([Yahoo]({yq('^TNX')}))"


def _headlines(b: Brief) -> list[str]:
    out = []
    for h in b.calendar.headlines:
        if h.source == "Federal Reserve" and not any(w in h.title.lower() for w in FED_HEADLINE_WORDS):
            continue  # routine Fed notices are not market news
        out.append(f"- Headline: {h.title} ({h.source})")
    return out[:3]


def _news(b: Brief) -> str:
    cal = b.calendar
    now_et = datetime.strptime(b.meta.as_of_pt, "%Y-%m-%d %H:%M").replace(tzinfo=config.PT).astimezone(config.ET).strftime("%H:%M")
    out = []
    if cal.events_today:
        out += ["Scheduled releases can move the index and option prices within seconds. High-impact ones matter most.", ""]
    for e in cal.events_today:
        done = ", already out" if e.time_et and e.time_et <= now_et and b.meta.post_type != "premarket" else ""
        src = f" ([source]({e.url}))" if e.url else ""
        out.append(f"- {both(e.time_et)}: {_event_name(e)} ({e.premium_relevance} impact{done}){src}")
    if not cal.events_today:
        out.append(f"- Nothing is scheduled today in the calendars ([BLS]({BLS_URL}) · [BEA]({BEA_URL}) · [Fed]({FED_URL}))")
    if b.meta.post_type == "premarket" or cal.earnings_prev_session:
        out.append(f"- Big-tech earnings last night: {', '.join(cal.earnings_prev_session) or 'none listed'} ([earnings]({EARNINGS_URL}))")
    other = _other_markets(b)
    if other:
        out.append(other)
    out += _headlines(b)
    return "\n".join(out)


def _sources(b: Brief) -> str:
    src = b.data_quality.sources
    times = sorted(datetime.fromisoformat(s.fetched_at_utc).astimezone(config.ET).strftime("%H:%M") for s in src if s.fetched_at_utc)
    when = ""
    if times:
        when = f" (fetched {both(times[0])})" if times[0] == times[-1] else with_pt(f" (fetched {times[0]}–{times[-1]} ET)")
    items = " · ".join(f"[{s.name}]({s.url}){'' if s.ok else ' (failed)'}" for s in src)
    gex = f"[vendor]({b.positioning.gex_vendor_url})" if b.positioning.gex_vendor_url else "vendor link not set"
    return (f"**Sources**{when}: {items}\n\nDealer gamma / GEX: not computed or estimated ({gex}).\n\n"
            f"New to a term? See the [glossary]({CONCEPT_BASE}glossary.html). More background: "
            + " · ".join(f"[{n}]({CONCEPT_BASE}{slug}.html)" for n, slug in CONCEPTS))


NARRATIVE_UNAVAILABLE = "*Narrative unavailable: this is the computed verdict.*"


def card(b: Brief, verdict: str | None = None, narrative: str | None = None) -> str:
    """The whole post body: Verdict (with what to watch), Technical, News / macro, sources."""
    blocks: list[str] = ["## Verdict", f"**{verdict or default_verdict(b)}**"]
    if meaning(b):
        blocks.append(meaning(b))
    w = watch(b)
    if w:
        blocks.append("\n".join(["What to watch:", ""] + [f"- {x}" for x in w]))
    if narrative:
        blocks.append(narrative.strip())
    pt = b.meta.post_type
    blocks.append("## Technical")
    if b.meta.market_closed_mode:
        blocks.append(_vol(b))
    elif pt == "premarket":
        blocks += [_overnight(b), _vol(b), _premium(b), _levels(b, None), _playbook(b)]
    else:
        blocks += [_regime_block(b), _now(b), _premium(b), _levels(b, 3), _playbook(b)]
    blocks += ["## News / macro", _news(b)]
    if b.data_quality.manual_inputs:
        blocks.append("**Still needed from you:** " + with_pt("; ".join(b.data_quality.manual_inputs)))
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
