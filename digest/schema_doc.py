"""Generate docs/brief-schema.md from the pydantic models + field descriptions.

`python -m digest.schema_doc` rewrites the doc; tests fail if a field is undocumented.
"""
from __future__ import annotations

from typing import Literal, get_args, get_origin

from pydantic import BaseModel

from digest import config
from digest.brief import Brief, Event, Headline, Level, SourceRef

D = {
    "meta.schema_version": "Brief schema version (semver-ish; bump on breaking change).",
    "meta.date": "Session date (YYYY-MM-DD, exchange calendar).",
    "meta.post_type": "premarket | midsession | afternoon.",
    "meta.version": "1 for the first post of this type today; 2, 3... for re-runs (files are never overwritten).",
    "meta.generated_at": "UTC ISO time the brief was computed.",
    "meta.data_as_of": "Timestamp of the latest intraday bar used (ET, ISO).",
    "meta.as_of_pt": "Wall-clock time the post is written for (PT).",
    "meta.session_open_pt": "Cash open (PT).",
    "meta.session_close_pt": "Cash close (PT); 10:00 on early-close days.",
    "meta.is_trading_day": "NYSE session today.",
    "meta.is_early_close": "NYSE early close today.",
    "meta.market_closed_mode": "Forced run on a non-trading day: only calendar/headlines/futures/FRED are meaningful.",
    "meta.spot_source": "How levels.spot was derived (SPX 5m, or ES-implied pre-market).",
    "levels.spot": "SPX last (pts). Pre-market: ES last minus es_spx_basis_pts.",
    "levels.prior_date": "Prior session date.",
    "levels.prior_open": "Prior session SPX open (pts).",
    "levels.prior_high": "Prior session SPX high (pts).",
    "levels.prior_low": "Prior session SPX low (pts).",
    "levels.prior_close": "Prior session SPX close (pts).",
    "levels.es_spx_basis_pts": "ES minus SPX at the prior 16:00 ET close (pts).",
    "levels.overnight_high": "ES high from prior 16:00 ET to the open, in SPX points (basis-adjusted).",
    "levels.overnight_low": "ES low over the same window, in SPX points.",
    "levels.overnight_range_pts": "overnight_high - overnight_low (pts).",
    "levels.gap_pts": "Open (or pre-market spot) minus prior close (pts).",
    "levels.gap_pct": "gap_pts as % of prior close.",
    "levels.gap_em_fraction": "gap_pts / vol.expected_move_day_pts (signed).",
    "levels.weekly_open": "Open of this week's first session (pts).",
    "levels.monthly_open": "Open of this month's first session (pts).",
    "levels.atr20_pts": "20-day average true range, prior sessions (pts).",
    "levels.adr10_pts": "10-day average high-low range (pts).",
    "levels.session_open": "Today's SPX open (pts); intraday posts.",
    "levels.session_high": "Today's high so far (pts).",
    "levels.session_low": "Today's low so far (pts).",
    "levels.range_used_pts": "session_high - session_low (pts).",
    "levels.range_used_atr_pct": "range_used_pts / atr20_pts x 100.",
    "vol.vix": "VIX level (latest, else prior close).",
    "vol.vix_change_pts": "VIX change vs prior close (pts).",
    "vol.vix_change_pct": "VIX change vs prior close (%).",
    "vol.vix9d": "VIX9D level.",
    "vol.vix3m": "VIX3M level.",
    "vol.vix6m": "VIX6M level.",
    "vol.vix9d_vix_ratio": "VIX9D / VIX (> 1: front-end backwardation).",
    "vol.vix_vix3m_ratio": "VIX / VIX3M (> 1: backwardation).",
    "vol.term_structure_label": "contango | flat | backwardation from VIX/VIX3M (flat = within 2%).",
    "vol.vvix": "VVIX level.",
    "vol.vvix_change_pct": "VVIX change vs prior close (%).",
    "vol.skew": "CBOE SKEW index.",
    "vol.rv10_pct": "10-day close-to-close realised vol, annualised (%).",
    "vol.rv20_pct": "20-day close-to-close realised vol, annualised (%).",
    "vol.vix_minus_rv20_pts": "VIX - RV20 (vol points): variance-risk-premium read.",
    "vol.expected_move_0dte_pts": "ATM 0DTE straddle now (pts). Intraday this prices only the remaining session.",
    "vol.expected_move_0dte_pct": "expected_move_0dte_pts as % of spot.",
    "vol.expected_move_day_pts": "Whole-session expected move (pts): the 09:35 ET print, else the premarket straddle, else the time-scaled current straddle.",
    "vol.expected_move_day_source": "Where expected_move_day_pts came from.",
    "vol.expected_move_weekly_pts": "ATM straddle for the next Friday expiry (pts).",
    "vol.expected_move_weekly_pct": "Weekly straddle as % of spot.",
    "vol.weekly_expiry": "Expiry used for the weekly straddle.",
    "vol.cboe_stats_date": "Session the CBOE put/call ratios refer to (prior session).",
    "vol.cboe_total_pcr": "CBOE total put/call ratio (volume).",
    "vol.cboe_index_pcr": "CBOE index put/call ratio.",
    "vol.cboe_equity_pcr": "CBOE equity put/call ratio.",
    "vol.cboe_spx_pcr": "CBOE SPX + SPXW put/call ratio.",
    "positioning.chain_source": "^SPX, or SPY when the fallback was used.",
    "positioning.chain_fallback_used": "True if SPY x10 was used.",
    "positioning.expiry_0dte": "Expiry of the 0DTE chain.",
    "positioning.pcr_volume_0dte": "0DTE put volume / call volume.",
    "positioning.pcr_oi_0dte": "0DTE put OI / call OI.",
    "positioning.call_oi_top_strikes": "Top 5 0DTE call strikes by OI (pts).",
    "positioning.put_oi_top_strikes": "Top 5 0DTE put strikes by OI (pts).",
    "positioning.nearest_oi_strike": "Top-OI strike nearest spot (pts).",
    "positioning.spot_to_nearest_oi_strike_pts": "spot - nearest_oi_strike (pts).",
    "cross_asset.es_change_pct": "ES vs prior daily close (%).",
    "cross_asset.nq_change_pct": "NQ vs prior daily close (%).",
    "cross_asset.rty_change_pct": "RTY vs prior daily close (%).",
    "cross_asset.us10y_yield_pct": "10y yield (^TNX, %).",
    "cross_asset.us10y_change_bp": "10y yield change vs prior close (bp).",
    "cross_asset.us5y_yield_pct": "5y yield (^FVX, %).",
    "cross_asset.us3m_yield_pct": "13-week bill yield (^IRX, %).",
    "cross_asset.dxy": "US dollar index level.",
    "cross_asset.dxy_change_pct": "DXY change (%).",
    "cross_asset.oil": "WTI front month (CL=F, $).",
    "cross_asset.oil_change_pct": "Oil change (%).",
    "cross_asset.gold": "Gold front month (GC=F, $).",
    "cross_asset.gold_change_pct": "Gold change (%).",
    "cross_asset.fred_as_of": "Latest FRED observation date used.",
    "cross_asset.fred_dgs10_pct": "FRED DGS10 (%).",
    "cross_asset.fred_dgs2_pct": "FRED DGS2 (%).",
    "cross_asset.fred_t10y2y_pct": "FRED T10Y2Y spread (%).",
    "cross_asset.fred_dff_pct": "FRED effective fed funds (%).",
    "cross_asset.fred_vixcls": "FRED VIXCLS (prior close cross-check).",
    "breadth.spy_change_pct": "SPY vs prior close (%), incl. pre-market prints.",
    "breadth.rsp_change_pct": "RSP (equal weight) change (%).",
    "breadth.rsp_minus_spy_pct": "RSP - SPY (%): > 0 = broad participation.",
    "breadth.qqq_change_pct": "QQQ change (%).",
    "breadth.iwm_change_pct": "IWM change (%).",
    "breadth.qqq_minus_iwm_pct": "QQQ - IWM (%): large-cap growth vs small caps.",
    "breadth.sectors_up_count": "Sector ETFs up on the day.",
    "breadth.sectors_total": "Sector ETFs with data (of 11).",
    "breadth.sector_ranking": "Sector ETFs best to worst.",
    "breadth.sector_change_pct": "Map: sector ETF -> % change.",
    "breadth.megacap_change_pct": "Map: mega-cap -> % change.",
    "breadth.megacap_avg_change_pct": "Equal-weight mean of mega-cap moves (%).",
    "calendar.events_today": "Today's events (records below).",
    "calendar.events_next_session": "Next session's events.",
    "calendar.next_session_date": "Next NYSE session date.",
    "calendar.next_fomc_date": "Next FOMC decision date.",
    "calendar.days_to_next_fomc": "Calendar days to next FOMC decision.",
    "calendar.high_event_later_today": "A high-relevance event is still ahead in today's session.",
    "calendar.next_high_event_time_et": "Time of that event (ET).",
    "calendar.headlines": "Top RSS titles (records below), newest first.",
    "intraday.minutes_since_open": "Minutes since the cash open.",
    "intraday.or_high": "Opening range (first 30 min) high (pts).",
    "intraday.or_low": "Opening range low (pts).",
    "intraday.or_complete": "First 30 minutes have elapsed.",
    "intraday.spot_vs_or": "inside | above | below the opening range (once complete).",
    "intraday.vwap": "Session VWAP (pts), SPY volume as proxy weights.",
    "intraday.vwap_method": "How VWAP was computed.",
    "intraday.spot_minus_vwap_pts": "spot - vwap (pts).",
    "intraday.rv_today_pct": "Realised vol so far today from 5-min returns, annualised (%).",
    "intraday.realized_range_em_fraction": "Today's range so far / expected_move_day_pts.",
    "intraday.high_retested": "Price returned to the session high after a pullback.",
    "intraday.low_retested": "Price returned to the session low after a bounce.",
    "data_quality.null_fields": "Fields unexpectedly null for this post type.",
    "data_quality.fallbacks": "Fallbacks used (SPY chain, ES-implied spot, proxy VWAP...).",
    "data_quality.source_errors": "Sources that failed after retries.",
    "data_quality.notes": "Other caveats (early close, empty calendar...).",
    "levels.range_position_pct": "Where spot sits in today's range: 0 = session low, 100 = session high.",
    "levels.prior_poc": "Prior session point of control (pts), volume-at-price.",
    "levels.prior_vah": "Prior session value area high (pts), 70% value area.",
    "levels.prior_val": "Prior session value area low (pts).",
    "levels.value_area_method": "How the value area was computed.",
    "levels.open_vs_prior_va": "Today's open (pre-market: indicated spot) above / inside / below the prior value area.",
    "levels.spot_vs_prior_va": "Spot above / inside / below the prior value area.",
    "levels.round_levels": "Round numbers (regime_rules.yaml levels.round_step_pts) within one expected move of spot.",
    "levels.level_stack": "All levels, high to low (records below), with confluence marked.",
    "vol.vix1d": "VIX1D level (latest, else prior close): the 0DTE-specific vol gauge.",
    "vol.vix1d_pctile_20d": "Percentile rank of VIX1D against its last 20 closes (0-100).",
    "vol.vix1d_20d_low": "Lowest VIX1D close of the last 20.",
    "vol.vix1d_20d_high": "Highest VIX1D close of the last 20.",
    "vol.vix1d_label": "low / normal / high / extreme from the percentile (thresholds in regime_rules.yaml).",
    "vol.iv_high": "VIX1D label is high or extreme.",
    "vol.straddle_strike": "Strike of the ATM straddle used for expected_move_0dte_pts.",
    "vol.straddle_quote_time_et": "Time the chain was fetched (HH:MM ET); quotes are delayed.",
    "vol.implied_range_low": "spot - straddle (pts).",
    "vol.implied_range_high": "spot + straddle (pts).",
    "vol.straddle_0935_pts": "The day's 09:35 ET ATM straddle print (pts): auto capture or manual entry.",
    "vol.straddle_0935_time_et": "Time of that print (HH:MM ET).",
    "vol.straddle_0935_source": "auto (chain) or manual.",
    "vol.iv_crush_pct": "Straddle now vs the 09:35 ET print (%), or the VIX1D-based estimate when there is no print.",
    "vol.iv_crush_label": "crush done at or below premium.crush_done_pct, else still elevated.",
    "vol.iv_crush_basis": "What iv_crush_pct is based on (straddle prints, or the labelled VIX1D estimate).",
    "vol.theta_extrinsic_remaining_pct": "ATM extrinsic remaining now under sqrt-of-time decay (%).",
    "positioning.gex_vendor_url": "Link slot for a dealer-gamma vendor page (GEX is not computed); null until set.",
    "calendar.earnings_prev_session": "Mega-cap earnings on the prior session date.",
    "calendar.data_day": "A high-relevance release or Fed event is on today's calendar.",
    "calendar.weekday": "Day of the week of the session.",
    "calendar.expiry_kind": "Largest options expiry today: daily (SPX's usual same-day options only), weekly (last session of the week), monthly (third Friday) or quarterly (third Friday of Mar/Jun/Sep/Dec).",
    "calendar.monthly_opex_date": "Next monthly options expiration on or after today (third Friday, or the session before it on a holiday).",
    "calendar.days_to_monthly_opex": "Calendar days to that expiration.",
    "calendar.opex_week": "Today is in the week of the monthly options expiration.",
    "calendar.vix_expiry_today": "VIX futures and options settle this morning.",
    "calendar.month_end": "Last trading day of the month.",
    "calendar.quarter_end": "Last trading day of the quarter.",
    "intraday.vwap_crosses": "5-min closes that crossed the running VWAP so far today.",
    "intraday.vwap_crosses_by_cutoff": "VWAP crosses up to vwap_cutoff_et (the count the day-type rules use).",
    "intraday.vwap_cutoff_et": "Cutoff for the VWAP rule (HH:MM ET).",
    "intraday.vwap_check_final": "The cutoff has passed, so the VWAP count is final.",
    "intraday.vwap_crossed_both_ways": "At least two VWAP crosses by the cutoff.",
    "intraday.vwap_above_frac": "Share of 5-min closes above VWAP up to the cutoff (0-1).",
    "intraday.snapshot_time_et": "Classification snapshot time (HH:MM ET); null before it.",
    "intraday.snapshot_spot": "SPX at the snapshot (pts).",
    "intraday.snapshot_vs_or": "Snapshot spot inside / above / below the opening range.",
    "intraday.snapshot_vs_prior_va": "Snapshot spot above / inside / below the prior value area.",
    "intraday.dev_poc": "Developing (today's) point of control (pts).",
    "intraday.dev_vah": "Developing value area high (pts).",
    "intraday.dev_val": "Developing value area low (pts).",
    "intraday.dev_poc_position": "Developing POC position in today's range (0 = low, 1 = high).",
    "intraday.cutoff_poc": "Most-traded price as of vwap_cutoff_et (or now, before it): the value the balance rule uses, so the label does not drift later.",
 "intraday.cutoff_poc_position": "Position of cutoff_poc in the range up to the cutoff (0 = low, 1 = high).",
 "intraday.profile_shape": "D / P / b / elongated (see concepts/volume-profile).",
    "intraday.accepted_outside_dev_va": "above / below when the last acceptance_closes 5-min closes are all beyond that developing value edge; else no.",
    "intraday.volume_ratio_recent": "Recent 5-min SPY volume / the 12:00-13:30 ET average (volume returning); null before 13:30 ET.",
    "regime.label": "trend_up / trend_down / balance / gap_and_go / gap_and_fill / undetermined.",
    "regime.lean": "Pre-classification lean: gap_up, gap_down, open_above_value, open_below_value, open_inside_value.",
    "regime.rules_fired": "Conditions that were met.",
    "regime.rules_failed": "Conditions that were not met.",
    "regime.conflicts": "Rule sets that point in opposite directions (label becomes undetermined).",
    "regime.prior_label": "Label from the earlier post today, if any.",
    "regime.confirmation": "first classification / confirmed / changed against prior_label.",
    "regime.holding": "Whether price now still supports the label.",
    "regime.holding_note": "What holding was judged on.",
    "playbook.live": "early / late / none / pending (pre-market).",
    "playbook.direction": "up / down when the regime gives one.",
    "playbook.instrument": "single leg, or the high-IV instrument from playbook.yaml.",
    "playbook.early_status": "Early playbook status and the reason.",
    "playbook.early_trigger": "Early trigger condition, when live.",
    "playbook.early_invalidation": "What invalidates the early trigger.",
    "playbook.early_window_et": "Early window (ET).",
    "playbook.early_time_stop_et": "Early time stop (ET).",
    "playbook.late_status": "Late playbook status and the reason.",
    "playbook.late_trigger": "The one late trigger that qualifies.",
    "playbook.late_window_et": "Late window (ET).",
    "playbook.flat_by_et": "Flat-by time (ET).",
    "playbook.premium_cap": "Late premium cap from playbook.yaml, or not set.",
    "playbook.reasons": "Why the playbook is in this state.",
    "playbook.flip": "What would flip the read.",
    "playbook.do_not": "The never list from playbook.yaml.",
    "data_quality.manual_inputs": "Values the user can type in because no free source supplied them.",
    "data_quality.sources": "Sources fetched for this run (records below).",
    "event.url": "Canonical schedule page for the event's source.",
    "level.name": "Level name.",
    "level.price": "Price (pts).",
    "level.kind": "prior / value / overnight / opening_range / vwap / session / developing / round.",
    "level.confluence": "Another level sits within levels.confluence_tolerance_pts.",
    "level.confluence_with": "Names of those levels.",
    "source.name": "Source label.",
    "source.url": "URL fetched (or the page behind a yfinance call).",
    "source.fetched_at_utc": "UTC ISO fetch time.",
    "source.ok": "False if the fetch failed.",
    "event.date": "YYYY-MM-DD.", "event.time_et": "HH:MM ET, null if unknown.", "event.name": "Description.",
    "event.category": "e.g. CPI, FOMC_DECISION, MEGACAP_EARNINGS, AUCTION_10Y_20Y_30Y, FED_SPEAKER.",
    "event.premium_relevance": "high | medium | low (mapping in regime_rules.yaml).",
    "headline.title": "Headline title only.", "headline.source": "Feed name.", "headline.published_utc": "UTC ISO time.",
}


def _type(ann) -> str:
    args = [a for a in get_args(ann) if a is not type(None)]
    if get_origin(ann) is Literal:
        return "enum: " + " / ".join(map(str, get_args(ann)))
    if args and get_origin(ann) not in (list, dict):
        return _type(args[0]) if len(args) == 1 else " | ".join(_type(a) for a in args)
    if get_origin(ann) is list:
        return f"list[{_type(get_args(ann)[0])}]"
    if get_origin(ann) is dict:
        return "map[str, float]"
    return getattr(ann, "__name__", str(ann)).replace("Event", "event").replace("Headline", "headline").replace("SourceRef", "source").replace("Level", "level")


def rows():
    for sec, field in Brief.model_fields.items():
        model = field.annotation
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            model = next(a for a in get_args(model) if isinstance(a, type) and issubclass(a, BaseModel))
        for name, f in model.model_fields.items():
            yield sec, name, _type(f.annotation), D.get(f"{sec}.{name}")
    for rec, model in (("event", Event), ("headline", Headline), ("level", Level), ("source", SourceRef)):
        for name, f in model.model_fields.items():
            yield rec, name, _type(f.annotation), D.get(f"{rec}.{name}")


def render() -> str:
    out = [
        "# brief.json schema",
        "",
        f"Current `schema_version`: **{config.SCHEMA_VERSION}**. Generated from `digest/brief.py` by `python -m digest.schema_doc` — do not edit by hand.",
        "",
        "Conventions: snake_case; units in field names (`_pts` SPX index points, `_pct` percent, `_bp` basis points, `_usd_bn` billions of dollars); "
        "sections are flat (one level deep); lists hold primitives or flat records (`event`, `headline`, `level`, `source`). Any value may be `null` when its source failed "
        "or it does not apply to the post type (intraday fields in a premarket post). Consumers should treat unknown fields as additive within a major version.",
        "",
        "Published at `data/YYYY-MM-DD/<post_type>.brief.json` and, for the latest post of each type, inside `api/latest.json` (static JSON, CORS-friendly on GitHub Pages).",
    ]
    cur = None
    for sec, name, typ, desc in rows():
        if sec != cur:
            out += ["", f"## `{sec}`" if sec not in ("event", "headline", "level", "source") else f"## record: `{sec}`", "", "| field | type | description |", "|---|---|---|"]
            cur = sec
        out.append(f"| `{name}` | {typ} | {(desc or '').replace('|', '/')} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (config.DOCS_DIR / "brief-schema.md").write_text(render())
    print("wrote docs/brief-schema.md")
