"""fetch -> raw.json -> brief.json -> regime. build_brief() is pure over the raw payload."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from digest import calendars, config, schedule
from digest.brief import (INTRADAY_ONLY_LEVELS, Breadth, Brief, Calendar, CrossAsset, DataQuality, Intraday, Levels,
                          Meta, Positioning, Vol)
from digest.fetch import market, web
from digest.fetch.base import now_utc_iso
from digest.indicators import Market, r2
from digest.indicators.events import events_for, high_event_later, next_fomc
from digest.indicators.intraday import compute_intraday
from digest.indicators.levels import compute_levels, spx_session_bars
from digest.indicators.market_stats import compute_breadth, compute_cboe, compute_cross_asset, compute_fred, compute_vol
from digest.indicators.options import compute_chain_stats
from digest.regime import classify, load_rules

log = logging.getLogger("digest.pipeline")


# --- Fetch -------------------------------------------------------------------------

def fetch_all(target: date, post_type: str, as_of: datetime) -> dict:
    sess = schedule.session(target)
    prev = schedule.prev_trading_day(target)
    nxt = schedule.next_trading_day(target)
    sources = {}
    sources["daily"] = market.fetch_daily(target)
    sources["intraday"] = market.fetch_intraday(target)
    sources["option_chain"] = market.fetch_option_chain(target) if sess else None
    sources["cboe"] = web.fetch_cboe_daily(prev)
    sources["fred"] = web.fetch_fred()
    sources["headlines"] = web.fetch_headlines()
    sources["fed_calendar"] = web.fetch_fed_calendar()
    sources["treasury_upcoming"] = web.fetch_treasury_upcoming()
    symbols = sorted(set(calendars.load_large_caps()) | set(config.MEGACAPS))
    sources["earnings"] = market.fetch_earnings(symbols)
    return {
        "schema_version": config.SCHEMA_VERSION,
        "date": target.isoformat(),
        "post_type": post_type,
        "as_of": as_of.isoformat(timespec="seconds"),
        "prev_trading_day": prev.isoformat(),
        "next_trading_day": nxt.isoformat(),
        "sources": {k: (v.to_json() if v is not None else None) for k, v in sources.items()},
    }


def _src(raw: dict, name: str):
    s = raw["sources"].get(name)
    return s["data"] if s and s.get("ok") else None


# --- Brief -------------------------------------------------------------------------

def _round_section(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, float):
            out[k] = r2(v)
        elif isinstance(v, list) and v and isinstance(v[0], float):
            out[k] = [r2(x) for x in v]
        else:
            out[k] = v
    return out


def _pick(d: dict, model) -> dict:
    return {k: v for k, v in d.items() if k in model.model_fields and v is not None}


def build_brief(raw: dict, rules: dict | None = None, version: int = 1, generated_at: str | None = None) -> Brief:
    rules = rules or load_rules()
    target = date.fromisoformat(raw["date"])
    post_type = raw["post_type"]
    as_of = datetime.fromisoformat(raw["as_of"])
    prev = date.fromisoformat(raw["prev_trading_day"])
    sess = schedule.session(target)
    closed = sess is None
    nxt = date.fromisoformat(raw["next_trading_day"])
    # On a closed day, evaluate everything against the next session's times.
    ref_sess = sess or schedule.session(nxt)
    open_et, close_et = ref_sess.open_et, ref_sess.close_et
    if closed:
        open_et = datetime.combine(target, open_et.timetz())
        close_et = datetime.combine(target, close_et.timetz())

    dq = DataQuality()
    for name, s in raw["sources"].items():
        if s and not s.get("ok"):
            dq.source_errors.append(f"{name}: {s.get('error')}")

    m = Market(_src(raw, "daily"), _src(raw, "intraday"), target, as_of)

    # Spot first (needed for the chain), then chain-derived EM (needed for the gap fraction).
    lv = compute_levels(m, prev, open_et, close_et, expected_move_pts=None)
    chain = _src(raw, "option_chain")
    chain_meta = (raw["sources"].get("option_chain") or {}).get("meta", {})
    ch: dict = {}
    if chain and lv.get("spot"):
        fb = bool(chain_meta.get("fallback"))
        ch = compute_chain_stats(chain, lv["spot"], as_of.astimezone(config.ET), close_et, fallback=fb)
        if fb:
            dq.fallbacks.append(f"^SPX chain unavailable ({chain_meta.get('primary_error')}); used SPY chain with strikes x{config.CHAIN_FALLBACK_SCALE:g}")
    day_em, day_em_src = day_expected_move(raw, ch, post_type, as_of, open_et, close_et)
    if day_em:
        ch["expected_move_day_pts"], ch["expected_move_day_source"] = day_em, day_em_src
        if day_em_src.startswith("time-scaled"):
            dq.fallbacks.append("day expected move time-scaled from the current 0DTE straddle (no premarket brief today)")
        if lv.get("gap_pts") is not None:
            lv["gap_em_fraction"] = lv["gap_pts"] / day_em
    if lv.get("spot_source", "").startswith("ES-implied"):
        dq.fallbacks.append("spot is ES-implied (cash index not open yet)")

    vol = {**compute_vol(m, open_et), **compute_cboe(_src(raw, "cboe")), **_pick(ch, Vol)}
    pos = _pick(ch, Positioning)
    xa = {**compute_cross_asset(m, open_et), **compute_fred(_src(raw, "fred"))}
    br = compute_breadth(m, open_et)

    sess_bars = spx_session_bars(m, open_et, close_et)
    intr: dict = {}
    if post_type != "premarket" and not closed:
        intr = compute_intraday(m, sess_bars, open_et, lv.get("spot"), lv.get("atr20_pts"), vol.get("expected_move_day_pts"),
                                rules.get("intraday", {}).get("retest_tolerance_atr_frac", 0.05))
        if intr.get("vwap_method") and "SPY" in intr["vwap_method"]:
            dq.fallbacks.append("VWAP uses SPY volume as a proxy (SPX has no volume)")

    # Calendar.
    cal_sources = {
        "fomc": calendars.load_fomc(target.year),
        "econ": calendars.load_econ(target.year),
        "auctions": calendars.load_auctions() + [
            {"date": a["auction_date"], "event": f"{a['security_term']} {a['security_type']} auction",
             "security_type": a["security_type"], "security_term": a["security_term"],
             "time_et": calendars._fed_time_to_hhmm((a.get("close_time_et") or "").replace("PM", "p.m.").replace("AM", "a.m."))}
            for a in (_src(raw, "treasury_upcoming") or [])
            if a.get("auction_date") and a.get("security_type") in ("Note", "Bond", "TIPS", "FRN")
        ],
        "fed_calendar": _src(raw, "fed_calendar"),
        "earnings": _src(raw, "earnings"),
    }
    ev_today = [] if closed else events_for(target, cal_sources, rules)
    ev_next = events_for(nxt, cal_sources, rules)
    nf_date, nf_days = next_fomc(cal_sources["fomc"], target)
    hel, hel_t = (False, None) if closed else high_event_later(ev_today, as_of, close_et)
    heads = (_src(raw, "headlines") or {}).get("items", [])[: config.HEADLINES_MAX]
    if not calendars.load_econ(target.year):
        dq.notes.append("econ calendar empty — run refresh-calendars")

    last_ts = m.last_intraday_ts()
    meta = Meta(
        date=raw["date"], post_type=post_type, version=version,
        generated_at=generated_at or now_utc_iso(),
        data_as_of=last_ts.isoformat() if last_ts is not None else None,
        as_of_pt=as_of.astimezone(config.PT).strftime("%Y-%m-%d %H:%M"),
        session_open_pt=None if closed else open_et.astimezone(config.PT).strftime("%H:%M"),
        session_close_pt=None if closed else close_et.astimezone(config.PT).strftime("%H:%M"),
        is_trading_day=not closed, is_early_close=bool(sess and sess.early_close),
        market_closed_mode=closed, spot_source=lv.get("spot_source"),
    )
    if meta.is_early_close:
        dq.notes.append(f"early close: session ends {meta.session_close_pt} PT")
    if chain is None and not closed:
        dq.notes.append("option chain unavailable — expected move, P/C and GEX are null")

    brief = Brief(
        meta=meta,
        levels=Levels(**_round_section(_pick(lv, Levels))),
        vol=Vol(**_round_section(_pick(vol, Vol))),
        positioning=Positioning(**_round_section(pos)),
        cross_asset=CrossAsset(**_round_section(_pick(xa, CrossAsset))),
        breadth=Breadth(**_round_section(_pick(br, Breadth))),
        calendar=Calendar(
            events_today=ev_today, events_next_session=ev_next, next_session_date=nxt.isoformat(),
            next_fomc_date=nf_date, days_to_next_fomc=nf_days,
            high_event_later_today=hel, next_high_event_time_et=hel_t, headlines=heads,
        ),
        intraday=Intraday(**_round_section(_pick(intr, Intraday))),
        data_quality=dq,
    )
    dq.null_fields = null_fields(brief)
    brief.regime = classify(brief, rules)
    return brief


def day_expected_move(raw: dict, ch: dict, post_type: str, as_of: datetime, open_et: datetime, close_et: datetime):
    """Expected move for the whole session. Intraday, the 0DTE straddle prices only the
    remaining move, so prefer the premarket brief's value; else scale by sqrt(time)."""
    ctx = raw.get("context") or {}
    if post_type != "premarket" and ctx.get("premarket_expected_move_0dte_pts"):
        return float(ctx["premarket_expected_move_0dte_pts"]), "premarket brief 0DTE straddle"
    em = ch.get("expected_move_0dte_pts")
    if not em:
        return None, None
    if post_type == "premarket" or as_of <= open_et:
        return em, "0DTE ATM straddle"
    total = (close_et - open_et).total_seconds() / 60
    remaining = max((close_et - as_of.astimezone(config.ET)).total_seconds() / 60, 15.0)
    return em * (total / remaining) ** 0.5, "time-scaled from current 0DTE straddle"


def null_fields(b: Brief) -> list[str]:
    """Scalar fields that are null *unexpectedly* for this post type."""
    skip_sections = {"meta", "regime", "data_quality", "calendar"}
    if b.meta.post_type == "premarket" or b.meta.market_closed_mode:
        skip_sections.add("intraday")
    out = []
    for sec, k, v in b.flat_items():
        if sec in skip_sections or v is not None:
            continue
        if sec == "levels" and k in INTRADAY_ONLY_LEVELS and (b.meta.post_type == "premarket" or b.meta.market_closed_mode):
            continue
        if b.meta.market_closed_mode and sec in ("positioning", "intraday"):
            continue
        out.append(f"{sec}.{k}")
    return out


def has_content(b: Brief) -> bool:
    """For market-closed runs: is there anything worth posting?"""
    if b.calendar.events_next_session:
        return True
    if b.cross_asset.es_change_pct is not None and b.meta.data_as_of:
        # Futures trading in the last hour counts as something to discuss.
        last = datetime.fromisoformat(b.meta.data_as_of)
        if datetime.now(config.UTC) - last < timedelta(hours=1):
            return True
    return False


def resolve_as_of(target: date, post_type: str, now: datetime) -> datetime:
    """Live runs use now; historical replays use the post's scheduled slot."""
    if target == now.astimezone(config.PT).date():
        return now.astimezone(config.PT)
    if schedule.session(target):
        return schedule.scheduled_time_pt(post_type, target)
    hh, mm = config.POST_TIMES_PT[post_type]
    return datetime.combine(target, time(hh, mm), tzinfo=config.PT)
