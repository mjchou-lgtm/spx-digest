"""brief.json schema (versioned). Documented in docs/brief-schema.md.

Rules: snake_case, units in field names, sections are flat (one level deep);
lists hold primitives or flat records (event, headline, level, source). Any value may be null when its source
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


class Level(_Flat):
    name: str
    price: float
    kind: str
    confluence: bool = False
    confluence_with: Optional[str] = None


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
    range_position_pct: F = None
    prior_poc: F = None
    prior_vah: F = None
    prior_val: F = None
    value_area_method: Optional[str] = None
    open_vs_prior_va: Optional[Literal["above", "inside", "below"]] = None
    spot_vs_prior_va: Optional[Literal["above", "inside", "below"]] = None
    round_levels: list[float] = []
    level_stack: list[Level] = []


class Vol(_Flat):
    vix: F = None
    vix_change_pts: F = None
    vix_change_pct: F = None
    vix1d: F = None
    vix1d_pctile_20d: F = None
    vix1d_20d_low: F = None
    vix1d_20d_high: F = None
    vix1d_label: Optional[Literal["low", "normal", "high", "extreme"]] = None
    iv_high: Optional[bool] = None
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
    straddle_strike: F = None
    straddle_quote_time_et: Optional[str] = None
    implied_range_low: F = None
    implied_range_high: F = None
    straddle_0935_pts: F = None
    straddle_0935_time_et: Optional[str] = None
    straddle_0935_source: Optional[str] = None
    iv_crush_pct: F = None
    iv_crush_label: Optional[Literal["crush done", "still elevated"]] = None
    iv_crush_basis: Optional[str] = None
    theta_extrinsic_remaining_pct: F = None
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
    gex_vendor_url: Optional[str] = None


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
    url: Optional[str] = None


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
    earnings_prev_session: list[str] = []
    data_day: bool = False
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
    vwap_crosses: Optional[int] = None
    vwap_crosses_by_cutoff: Optional[int] = None
    vwap_cutoff_et: Optional[str] = None
    vwap_check_final: Optional[bool] = None
    vwap_crossed_both_ways: Optional[bool] = None
    vwap_above_frac: F = None
    snapshot_time_et: Optional[str] = None
    snapshot_spot: F = None
    snapshot_vs_or: Optional[Literal["inside", "above", "below"]] = None
    snapshot_vs_prior_va: Optional[Literal["above", "inside", "below"]] = None
    dev_poc: F = None
    dev_vah: F = None
    dev_val: F = None
    dev_poc_position: F = None
    profile_shape: Optional[Literal["D", "P", "b", "elongated"]] = None
    accepted_outside_dev_va: Optional[Literal["above", "below", "no"]] = None
    volume_ratio_recent: F = None


REGIME_LABELS = ("trend_up", "trend_down", "balance", "gap_and_go", "gap_and_fill", "undetermined")


class Regime(_Flat):
    label: Literal["trend_up", "trend_down", "balance", "gap_and_go", "gap_and_fill", "undetermined"]
    lean: Optional[str] = None
    rules_fired: list[str] = []
    rules_failed: list[str] = []
    conflicts: list[str] = []
    prior_label: Optional[str] = None
    confirmation: Optional[Literal["first classification", "confirmed", "changed"]] = None
    holding: Optional[bool] = None
    holding_note: Optional[str] = None


class Playbook(_Flat):
    live: Literal["early", "late", "none", "pending"]
    direction: Optional[Literal["up", "down"]] = None
    instrument: Optional[str] = None
    early_status: Optional[str] = None
    early_trigger: Optional[str] = None
    early_invalidation: Optional[str] = None
    early_window_et: Optional[str] = None
    early_time_stop_et: Optional[str] = None
    late_status: Optional[str] = None
    late_trigger: Optional[str] = None
    late_window_et: Optional[str] = None
    flat_by_et: Optional[str] = None
    premium_cap: Optional[str] = None
    reasons: list[str] = []
    flip: list[str] = []
    do_not: list[str] = []


class SourceRef(_Flat):
    name: str
    url: str
    fetched_at_utc: Optional[str] = None
    ok: bool = True


class DataQuality(_Flat):
    null_fields: list[str] = []
    fallbacks: list[str] = []
    source_errors: list[str] = []
    notes: list[str] = []
    manual_inputs: list[str] = []
    sources: list[SourceRef] = []


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
    playbook: Optional[Playbook] = None
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
