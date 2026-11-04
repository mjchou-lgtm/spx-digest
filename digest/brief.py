"""brief.json schema (versioned). Documented in docs/brief-schema.md.

Rules: snake_case, units in field names, sections are flat (one level deep);
lists hold primitives or flat records. Any value may be null when its source
failed or does not apply (e.g. intraday fields in a premarket post).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from digest.config import SCHEMA_VERSION

F = Optional[float]


class _Flat(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(_Flat):
    schema_version: str = SCHEMA_VERSION
    date: str
    post_type: Literal["premarket", "midsession", "afternoon"]
    version: int = 1
    generated_at: str
    data_as_of: Optional[str] = None
    as_of_pt: str
    session_open_pt: Optional[str] = None
    session_close_pt: Optional[str] = None
    is_trading_day: bool
    is_early_close: bool = False
    market_closed_mode: bool = False
    spot_source: Optional[str] = None


class Levels(_Flat):
    spot: F = None
    prior_date: Optional[str] = None
    prior_open: F = None
    prior_high: F = None
    prior_low: F = None
    prior_close: F = None
    es_spx_basis_pts: F = None
    overnight_high: F = None
    overnight_low: F = None
    overnight_range_pts: F = None
    gap_pts: F = None
    gap_pct: F = None
    gap_em_fraction: F = None
    weekly_open: F = None
    monthly_open: F = None
    atr20_pts: F = None
    adr10_pts: F = None
    session_open: F = None
    session_high: F = None
    session_low: F = None
    range_used_pts: F = None
    range_used_atr_pct: F = None


class Vol(_Flat):
    vix: F = None
    vix_change_pts: F = None
    vix_change_pct: F = None
    vix9d: F = None
    vix3m: F = None
    vix6m: F = None
    vix9d_vix_ratio: F = None
    vix_vix3m_ratio: F = None
    term_structure_label: Optional[Literal["contango", "flat", "backwardation"]] = None
    vvix: F = None
    vvix_change_pct: F = None
    skew: F = None
    rv10_pct: F = None
    rv20_pct: F = None
    vix_minus_rv20_pts: F = None
    expected_move_0dte_pts: F = None
    expected_move_0dte_pct: F = None
    expected_move_day_pts: F = None
    expected_move_day_source: Optional[str] = None
    expected_move_weekly_pts: F = None
    expected_move_weekly_pct: F = None
    weekly_expiry: Optional[str] = None
    cboe_stats_date: Optional[str] = None
    cboe_total_pcr: F = None
    cboe_index_pcr: F = None
    cboe_equity_pcr: F = None
    cboe_spx_pcr: F = None


class Positioning(_Flat):
    chain_source: Optional[str] = None
    chain_fallback_used: bool = False
    expiry_0dte: Optional[str] = None
    pcr_volume_0dte: F = None
    pcr_oi_0dte: F = None
    call_oi_top_strikes: list[float] = []
    put_oi_top_strikes: list[float] = []
    nearest_oi_strike: F = None
    spot_to_nearest_oi_strike_pts: F = None
    net_gex_at_spot_usd_bn: F = None
    gamma_flip_approx: F = None
    spot_vs_gamma_flip_pts: F = None
    spot_vs_gamma_flip: Optional[Literal["above", "below"]] = None
    gex_method: str = "approximate, OI-based (OI x BS gamma x 100 x spot^2 x 0.01; calls +, puts -). Not dealer positioning."


class CrossAsset(_Flat):
    es_change_pct: F = None
    nq_change_pct: F = None
    rty_change_pct: F = None
    us10y_yield_pct: F = None
    us10y_change_bp: F = None
    us5y_yield_pct: F = None
    us3m_yield_pct: F = None
    dxy: F = None
    dxy_change_pct: F = None
    oil: F = None
    oil_change_pct: F = None
    gold: F = None
    gold_change_pct: F = None
    fred_as_of: Optional[str] = None
    fred_dgs10_pct: F = None
    fred_dgs2_pct: F = None
    fred_t10y2y_pct: F = None
    fred_dff_pct: F = None
    fred_vixcls: F = None


class Breadth(_Flat):
    spy_change_pct: F = None
    rsp_change_pct: F = None
    rsp_minus_spy_pct: F = None
    qqq_change_pct: F = None
    iwm_change_pct: F = None
    qqq_minus_iwm_pct: F = None
    sectors_up_count: Optional[int] = None
    sectors_total: Optional[int] = None
    sector_ranking: list[str] = []
    sector_change_pct: dict[str, float] = {}
    megacap_change_pct: dict[str, float] = {}
    megacap_avg_change_pct: F = None


class Event(_Flat):
    date: str
    time_et: Optional[str] = None
    name: str
    category: str
    premium_relevance: Literal["high", "medium", "low"]


class Headline(_Flat):
    title: str
    source: str
    published_utc: Optional[str] = None


class Calendar(_Flat):
    events_today: list[Event] = []
    events_next_session: list[Event] = []
    next_session_date: Optional[str] = None
    next_fomc_date: Optional[str] = None
    days_to_next_fomc: Optional[int] = None
    high_event_later_today: bool = False
    next_high_event_time_et: Optional[str] = None
    headlines: list[Headline] = []


class Intraday(_Flat):
    minutes_since_open: Optional[int] = None
    or_high: F = None
    or_low: F = None
    or_complete: bool = False
    spot_vs_or: Optional[Literal["inside", "above", "below"]] = None
    vwap: F = None
    vwap_method: Optional[str] = None
    spot_minus_vwap_pts: F = None
    rv_today_pct: F = None
    realized_range_em_fraction: F = None
    high_retested: Optional[bool] = None
    low_retested: Optional[bool] = None


class Regime(_Flat):
    label: Literal["TREND_UP", "TREND_DOWN", "RANGE", "EVENT_WAIT", "VOL_EXPANSION", "NO_TRADE"]
    confidence: Literal["low", "medium", "high"]
    rules_fired: list[str] = []
    scores: dict[str, float] = {}


class DataQuality(_Flat):
    null_fields: list[str] = []
    fallbacks: list[str] = []
    source_errors: list[str] = []
    notes: list[str] = []


class Brief(_Flat):
    meta: Meta
    levels: Levels
    vol: Vol
    positioning: Positioning
    cross_asset: CrossAsset
    breadth: Breadth
    calendar: Calendar
    intraday: Intraday
    regime: Optional[Regime] = None
    data_quality: DataQuality

    def flat_items(self, sections: tuple[str, ...] | None = None):
        """(section, field, value) for scalar fields — used for tables and null scans."""
        for sec_name, sec in self:
            if sections and sec_name not in sections:
                continue
            if not isinstance(sec, BaseModel):
                continue
            for k, v in sec:
                yield sec_name, k, v


# Sections whose null fields are expected (not a data-quality issue) by post type.
INTRADAY_ONLY_LEVELS = {"session_open", "session_high", "session_low", "range_used_pts", "range_used_atr_pct"}
