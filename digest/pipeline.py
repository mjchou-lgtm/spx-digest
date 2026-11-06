"""fetch -> raw.json -> brief.json -> regime. build_brief() is pure over the raw payload."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from digest import calendars, config, schedule
from digest import playbook as playbook_mod
from digest.brief import (INTRADAY_ONLY_LEVELS, Breadth, Brief, Calendar, CrossAsset, DataQuality, Intraday, Levels,
                          Meta, Positioning, SourceRef, Vol)
from digest.fetch import market, web
from digest.fetch.base import now_utc_iso
from digest.indicators import Market, r2
from digest.indicators.events import events_for, high_event_later, next_fomc
from digest.indicators import premium
from digest.indicators.intraday import compute_intraday, compute_structure
from digest.indicators.levels import build_level_stack, compute_levels, spx_session_bars
from digest.indicators.profile import session_profile, side_of
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
    sources["ff_calendar"] = web.fetch_ff_calendar()
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


SOURCE_PAGES = {
    "daily": ("Yahoo daily bars", "https://finance.yahoo.com/quote/%5EGSPC/history"),
    "intraday": ("Yahoo 5-min bars", "https://finance.yahoo.com/quote/%5EGSPC/chart"),
    "option_chain": ("Yahoo SPX chain", "https://finance.yahoo.com/quote/%5ESPX/options"),
    "cboe": ("Cboe daily stats", None),
    "fred": ("FRED", "https://fred.stlouisfed.org/"),
    "fed_calendar": ("Fed calendar", config.FED_CALENDAR_URL),
    "treasury_upcoming": ("TreasuryDirect auctions", config.TREASURY_UPCOMING_URL),
    "earnings": ("Yahoo earnings dates", "https://finance.yahoo.com/calendar/earnings"),
    "ff_calendar": ("ForexFactory calendar", config.FF_CALENDAR_URL),
}


def source_refs(raw: dict) -> list[SourceRef]:
    out = []
    for name, s in raw["sources"].items():
        if not s:
            continue
        if name == "headlines":
            out += [SourceRef(name=f"RSS: {n}", url=u, fetched_at_utc=s.get("fetched_at"), ok=bool(s.get("ok"))) for n, u in config.RSS_FEEDS.items()]
            continue
        label, url = SOURCE_PAGES.get(name, (name, None))
        url = (s.get("meta") or {}).get("url") or url
        if url:
            out.append(SourceRef(name=label, url=url, fetched_at_utc=s.get("fetched_at"), ok=bool(s.get("ok"))))
    return out


def build_brief(raw: dict, rules: dict | None = None, version: int = 1, generated_at: str | None = None, pb: dict | None = None) -> Brief:
    rules = rules or load_rules()
    ctx = raw.get("context") or {}
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
        ch = compute_chain_stats(chain, lv["spot"], fallback=fb)
        fetched = (raw["sources"].get("option_chain") or {}).get("fetched_at")
        if fetched and ch.get("expected_move_0dte_pts"):
            ch["straddle_quote_time_et"] = datetime.fromisoformat(fetched).astimezone(config.ET).strftime("%H:%M")
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

    # Prior-day value area (volume-at-price from 5-min bars).
    prev_sess = schedule.session(prev)
    spy = m.intra.get("SPY")
    if prev_sess:
        p_spx = spx_session_bars(m, prev_sess.open_et, prev_sess.close_et)
        p_spy = spy[(spy.index >= prev_sess.open_et) & (spy.index < prev_sess.close_et)] if spy is not None else None
        prof, method = session_profile(p_spx, p_spy, lv.get("prior_close"))
        if prof:
            lv.update(prior_poc=prof["poc"], prior_vah=prof["vah"], prior_val=prof["val"], value_area_method=method)
    lv["open_vs_prior_va"] = side_of(lv.get("session_open") or lv.get("spot"), lv.get("prior_vah"), lv.get("prior_val"))
    lv["spot_vs_prior_va"] = side_of(lv.get("spot"), lv.get("prior_vah"), lv.get("prior_val"))
    if lv.get("range_used_pts"):
        lv["range_position_pct"] = (lv["spot"] - lv["session_low"]) / lv["range_used_pts"] * 100

    prm = rules["premium"]
    vol = {**compute_vol(m, open_et), **compute_cboe(_src(raw, "cboe")), **_pick(ch, Vol)}
    vol.update(premium.vix1d_stats(m, vol.get("vix1d"), prm))
    if not closed:
        vol["theta_extrinsic_remaining_pct"] = premium.extrinsic_remaining_pct(as_of.astimezone(config.ET), open_et, close_et)
    s0935 = ctx.get("straddle_0935") or {}
    if s0935.get("pts"):
        vol.update(straddle_0935_pts=float(s0935["pts"]), straddle_0935_time_et=s0935.get("time_et"), straddle_0935_source=s0935.get("source"))
    if post_type != "premarket" and not closed:
        cr = premium.crush(vol.get("expected_move_0dte_pts"), vol.get("straddle_0935_pts"), prm["crush_done_pct"])
        if not cr and (pb or playbook_mod.load_playbook())["early"].get("allow_vix1d_crush_estimate"):
            cr = premium.crush_estimate_from_vix1d(m, open_et, close_et, prm["crush_done_pct"])
            if cr:
                dq.fallbacks.append("IV crush is an estimate from VIX1D (no 09:35 ET straddle print for today)")
        vol.update(cr)
        if not vol.get("straddle_0935_pts"):
            dq.manual_inputs.append("09:35 ET straddle print (Generate page, or python -m digest straddle --set PRICE)")
    pos = _pick(ch, Positioning)
    pos["gex_vendor_url"] = config.GEX_VENDOR_URL or None
    xa = {**compute_cross_asset(m, open_et), **compute_fred(_src(raw, "fred"))}
    br = compute_breadth(m, open_et)

    sess_bars = spx_session_bars(m, open_et, close_et)
    intr: dict = {}
    if post_type != "premarket" and not closed:
        intr = compute_intraday(m, sess_bars, open_et, lv.get("spot"), lv.get("atr20_pts"), vol.get("expected_move_day_pts"),
                                rules.get("intraday", {}).get("retest_tolerance_atr_frac", 0.05))
        intr.update(compute_structure(m, sess_bars, open_et, lv.get("prior_vah"), lv.get("prior_val"), rules["classify"]))
        if intr.get("vwap_method") and "SPY" in intr["vwap_method"]:
            dq.fallbacks.append("VWAP and volume profile use SPY volume as a proxy (SPX has no volume)")
    stack, rounds = build_level_stack(lv, intr, rules["levels"]["confluence_tolerance_pts"], rules["levels"]["round_step_pts"],
                                      vol.get("expected_move_day_pts") or vol.get("expected_move_0dte_pts") or lv.get("atr20_pts"))
    lv["level_stack"], lv["round_levels"] = stack, rounds

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
        "ff_calendar": _src(raw, "ff_calendar"),
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
        dq.notes.append("option chain unavailable: straddle, expected move and put/call ratios are null")
        dq.manual_inputs.append("ATM straddle (no free quote this run; read it from Cboe delayed quotes)")
    dq.sources = source_refs(raw)
    earn_prev = list(ctx.get("prev_session_earnings") or []) or [
        e["name"] for e in events_for(prev, cal_sources, rules) if e["category"] == "MEGACAP_EARNINGS"]

    brief = Brief(
        meta=meta,
        levels=Levels(**_round_section(_pick(lv, Levels))),
        vol=Vol(**_round_section(_pick(vol, Vol))),
        positioning=Positioning(**_round_section(pos)),
        cross_asset=CrossAsset(**_round_section(_pick(xa, CrossAsset))),
        breadth=Breadth(**_round_section(_pick(br, Breadth))),
        calendar=Calendar(
            events_today=ev_today, events_next_session=ev_next, next_session_date=nxt.isoformat(),
            next_fomc_date=nf_date, days_to_next_fomc=nf_days, earnings_prev_session=earn_prev,
            data_day=any(e["premium_relevance"] == "high" and e["category"] not in ("MEGACAP_EARNINGS",) for e in ev_today),
            high_event_later_today=hel, next_high_event_time_et=hel_t, headlines=heads,
        ),
        intraday=Intraday(**_round_section(_pick(intr, Intraday))),
        data_quality=dq,
    )
    dq.null_fields = null_fields(brief)
    brief.regime = classify(brief, rules, prior_label=ctx.get("prior_regime_label"))
    brief.playbook = playbook_mod.evaluate(brief, rules, pb)
    return brief


def day_expected_move(raw: dict, ch: dict, post_type: str, as_of: datetime, open_et: datetime, close_et: datetime):
    """Expected move for the whole session. Intraday, the 0DTE straddle prices only the
    remaining move, so prefer the premarket brief's value; else scale by sqrt(time)."""
    ctx = raw.get("context") or {}
    if post_type != "premarket" and (ctx.get("straddle_0935") or {}).get("pts"):
        return float(ctx["straddle_0935"]["pts"]), "09:35 ET straddle print"
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
    skip_sections = {"meta", "regime", "playbook", "data_quality", "calendar"}
    if b.meta.post_type == "premarket" or b.meta.market_closed_mode:
        skip_sections.add("intraday")
    pre = b.meta.post_type == "premarket" or b.meta.market_closed_mode
    expected = {"positioning.gex_vendor_url", "vol.straddle_0935_time_et", "vol.straddle_0935_source", "vol.iv_crush_basis",
                "intraday.volume_ratio_recent", "intraday.accepted_outside_dev_va"}
    if pre:
        expected |= {"vol.straddle_0935_pts", "vol.iv_crush_pct", "vol.iv_crush_label", "levels.range_position_pct"}
    if b.meta.market_closed_mode:
        expected |= {"vol.theta_extrinsic_remaining_pct"}
    out = []
    for sec, k, v in b.flat_items():
        if sec in skip_sections or v is not None or f"{sec}.{k}" in expected:
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
