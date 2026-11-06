# brief.json schema

Current `schema_version`: **2.0**. Generated from `digest/brief.py` by `python -m digest.schema_doc` — do not edit by hand.

Conventions: snake_case; units in field names (`_pts` SPX index points, `_pct` percent, `_bp` basis points, `_usd_bn` billions of dollars); sections are flat (one level deep); lists hold primitives or flat records (`event`, `headline`, `level`, `source`). Any value may be `null` when its source failed or it does not apply to the post type (intraday fields in a premarket post). Consumers should treat unknown fields as additive within a major version.

Published at `data/YYYY-MM-DD/<post_type>.brief.json` and, for the latest post of each type, inside `api/latest.json` (static JSON, CORS-friendly on GitHub Pages).

## `meta`

| field | type | description |
|---|---|---|
| `schema_version` | str | Brief schema version (semver-ish; bump on breaking change). |
| `date` | str | Session date (YYYY-MM-DD, exchange calendar). |
| `post_type` | enum: premarket / midsession / afternoon | premarket / midsession / afternoon. |
| `version` | int | 1 for the first post of this type today; 2, 3... for re-runs (files are never overwritten). |
| `generated_at` | str | UTC ISO time the brief was computed. |
| `data_as_of` | str | Timestamp of the latest intraday bar used (ET, ISO). |
| `as_of_pt` | str | Wall-clock time the post is written for (PT). |
| `session_open_pt` | str | Cash open (PT). |
| `session_close_pt` | str | Cash close (PT); 10:00 on early-close days. |
| `is_trading_day` | bool | NYSE session today. |
| `is_early_close` | bool | NYSE early close today. |
| `market_closed_mode` | bool | Forced run on a non-trading day: only calendar/headlines/futures/FRED are meaningful. |
| `spot_source` | str | How levels.spot was derived (SPX 5m, or ES-implied pre-market). |

## `levels`

| field | type | description |
|---|---|---|
| `spot` | float | SPX last (pts). Pre-market: ES last minus es_spx_basis_pts. |
| `prior_date` | str | Prior session date. |
| `prior_open` | float | Prior session SPX open (pts). |
| `prior_high` | float | Prior session SPX high (pts). |
| `prior_low` | float | Prior session SPX low (pts). |
| `prior_close` | float | Prior session SPX close (pts). |
| `es_spx_basis_pts` | float | ES minus SPX at the prior 16:00 ET close (pts). |
| `overnight_high` | float | ES high from prior 16:00 ET to the open, in SPX points (basis-adjusted). |
| `overnight_low` | float | ES low over the same window, in SPX points. |
| `overnight_range_pts` | float | overnight_high - overnight_low (pts). |
| `gap_pts` | float | Open (or pre-market spot) minus prior close (pts). |
| `gap_pct` | float | gap_pts as % of prior close. |
| `gap_em_fraction` | float | gap_pts / vol.expected_move_day_pts (signed). |
| `weekly_open` | float | Open of this week's first session (pts). |
| `monthly_open` | float | Open of this month's first session (pts). |
| `atr20_pts` | float | 20-day average true range, prior sessions (pts). |
| `adr10_pts` | float | 10-day average high-low range (pts). |
| `session_open` | float | Today's SPX open (pts); intraday posts. |
| `session_high` | float | Today's high so far (pts). |
| `session_low` | float | Today's low so far (pts). |
| `range_used_pts` | float | session_high - session_low (pts). |
| `range_used_atr_pct` | float | range_used_pts / atr20_pts x 100. |
| `range_position_pct` | float | Where spot sits in today's range: 0 = session low, 100 = session high. |
| `prior_poc` | float | Prior session point of control (pts), volume-at-price. |
| `prior_vah` | float | Prior session value area high (pts), 70% value area. |
| `prior_val` | float | Prior session value area low (pts). |
| `value_area_method` | str | How the value area was computed. |
| `open_vs_prior_va` | enum: above / inside / below | Today's open (pre-market: indicated spot) above / inside / below the prior value area. |
| `spot_vs_prior_va` | enum: above / inside / below | Spot above / inside / below the prior value area. |
| `round_levels` | list[float] | Round numbers (regime_rules.yaml levels.round_step_pts) within one expected move of spot. |
| `level_stack` | list[level] | All levels, high to low (records below), with confluence marked. |

## `vol`

| field | type | description |
|---|---|---|
| `vix` | float | VIX level (latest, else prior close). |
| `vix_change_pts` | float | VIX change vs prior close (pts). |
| `vix_change_pct` | float | VIX change vs prior close (%). |
| `vix1d` | float | VIX1D level (latest, else prior close): the 0DTE-specific vol gauge. |
| `vix1d_pctile_20d` | float | Percentile rank of VIX1D against its last 20 closes (0-100). |
| `vix1d_20d_low` | float | Lowest VIX1D close of the last 20. |
| `vix1d_20d_high` | float | Highest VIX1D close of the last 20. |
| `vix1d_label` | enum: low / normal / high / extreme | low / normal / high / extreme from the percentile (thresholds in regime_rules.yaml). |
| `iv_high` | bool | VIX1D label is high or extreme. |
| `vix9d` | float | VIX9D level. |
| `vix3m` | float | VIX3M level. |
| `vix6m` | float | VIX6M level. |
| `vix9d_vix_ratio` | float | VIX9D / VIX (> 1: front-end backwardation). |
| `vix_vix3m_ratio` | float | VIX / VIX3M (> 1: backwardation). |
| `term_structure_label` | enum: contango / flat / backwardation | contango / flat / backwardation from VIX/VIX3M (flat = within 2%). |
| `vvix` | float | VVIX level. |
| `vvix_change_pct` | float | VVIX change vs prior close (%). |
| `skew` | float | CBOE SKEW index. |
| `rv10_pct` | float | 10-day close-to-close realised vol, annualised (%). |
| `rv20_pct` | float | 20-day close-to-close realised vol, annualised (%). |
| `vix_minus_rv20_pts` | float | VIX - RV20 (vol points): variance-risk-premium read. |
| `expected_move_0dte_pts` | float | ATM 0DTE straddle now (pts). Intraday this prices only the remaining session. |
| `expected_move_0dte_pct` | float | expected_move_0dte_pts as % of spot. |
| `straddle_strike` | float | Strike of the ATM straddle used for expected_move_0dte_pts. |
| `straddle_quote_time_et` | str | Time the chain was fetched (HH:MM ET); quotes are delayed. |
| `implied_range_low` | float | spot - straddle (pts). |
| `implied_range_high` | float | spot + straddle (pts). |
| `straddle_0935_pts` | float | The day's 09:35 ET ATM straddle print (pts): auto capture or manual entry. |
| `straddle_0935_time_et` | str | Time of that print (HH:MM ET). |
| `straddle_0935_source` | str | auto (chain) or manual. |
| `iv_crush_pct` | float | Straddle now vs the 09:35 ET print (%), or the VIX1D-based estimate when there is no print. |
| `iv_crush_label` | enum: crush done / still elevated | crush done at or below premium.crush_done_pct, else still elevated. |
| `iv_crush_basis` | str | What iv_crush_pct is based on (straddle prints, or the labelled VIX1D estimate). |
| `theta_extrinsic_remaining_pct` | float | ATM extrinsic remaining now under sqrt-of-time decay (%). |
| `expected_move_day_pts` | float | Whole-session expected move (pts): the 09:35 ET print, else the premarket straddle, else the time-scaled current straddle. |
| `expected_move_day_source` | str | Where expected_move_day_pts came from. |
| `expected_move_weekly_pts` | float | ATM straddle for the next Friday expiry (pts). |
| `expected_move_weekly_pct` | float | Weekly straddle as % of spot. |
| `weekly_expiry` | str | Expiry used for the weekly straddle. |
| `cboe_stats_date` | str | Session the CBOE put/call ratios refer to (prior session). |
| `cboe_total_pcr` | float | CBOE total put/call ratio (volume). |
| `cboe_index_pcr` | float | CBOE index put/call ratio. |
| `cboe_equity_pcr` | float | CBOE equity put/call ratio. |
| `cboe_spx_pcr` | float | CBOE SPX + SPXW put/call ratio. |

## `positioning`

| field | type | description |
|---|---|---|
| `chain_source` | str | ^SPX, or SPY when the fallback was used. |
| `chain_fallback_used` | bool | True if SPY x10 was used. |
| `expiry_0dte` | str | Expiry of the 0DTE chain. |
| `pcr_volume_0dte` | float | 0DTE put volume / call volume. |
| `pcr_oi_0dte` | float | 0DTE put OI / call OI. |
| `call_oi_top_strikes` | list[float] | Top 5 0DTE call strikes by OI (pts). |
| `put_oi_top_strikes` | list[float] | Top 5 0DTE put strikes by OI (pts). |
| `nearest_oi_strike` | float | Top-OI strike nearest spot (pts). |
| `spot_to_nearest_oi_strike_pts` | float | spot - nearest_oi_strike (pts). |
| `gex_vendor_url` | str | Link slot for a dealer-gamma vendor page (GEX is not computed); null until set. |

## `cross_asset`

| field | type | description |
|---|---|---|
| `es_change_pct` | float | ES vs prior daily close (%). |
| `nq_change_pct` | float | NQ vs prior daily close (%). |
| `rty_change_pct` | float | RTY vs prior daily close (%). |
| `us10y_yield_pct` | float | 10y yield (^TNX, %). |
| `us10y_change_bp` | float | 10y yield change vs prior close (bp). |
| `us5y_yield_pct` | float | 5y yield (^FVX, %). |
| `us3m_yield_pct` | float | 13-week bill yield (^IRX, %). |
| `dxy` | float | US dollar index level. |
| `dxy_change_pct` | float | DXY change (%). |
| `oil` | float | WTI front month (CL=F, $). |
| `oil_change_pct` | float | Oil change (%). |
| `gold` | float | Gold front month (GC=F, $). |
| `gold_change_pct` | float | Gold change (%). |
| `fred_as_of` | str | Latest FRED observation date used. |
| `fred_dgs10_pct` | float | FRED DGS10 (%). |
| `fred_dgs2_pct` | float | FRED DGS2 (%). |
| `fred_t10y2y_pct` | float | FRED T10Y2Y spread (%). |
| `fred_dff_pct` | float | FRED effective fed funds (%). |
| `fred_vixcls` | float | FRED VIXCLS (prior close cross-check). |

## `breadth`

| field | type | description |
|---|---|---|
| `spy_change_pct` | float | SPY vs prior close (%), incl. pre-market prints. |
| `rsp_change_pct` | float | RSP (equal weight) change (%). |
| `rsp_minus_spy_pct` | float | RSP - SPY (%): > 0 = broad participation. |
| `qqq_change_pct` | float | QQQ change (%). |
| `iwm_change_pct` | float | IWM change (%). |
| `qqq_minus_iwm_pct` | float | QQQ - IWM (%): large-cap growth vs small caps. |
| `sectors_up_count` | int | Sector ETFs up on the day. |
| `sectors_total` | int | Sector ETFs with data (of 11). |
| `sector_ranking` | list[str] | Sector ETFs best to worst. |
| `sector_change_pct` | map[str, float] | Map: sector ETF -> % change. |
| `megacap_change_pct` | map[str, float] | Map: mega-cap -> % change. |
| `megacap_avg_change_pct` | float | Equal-weight mean of mega-cap moves (%). |

## `calendar`

| field | type | description |
|---|---|---|
| `events_today` | list[event] | Today's events (records below). |
| `events_next_session` | list[event] | Next session's events. |
| `next_session_date` | str | Next NYSE session date. |
| `next_fomc_date` | str | Next FOMC decision date. |
| `days_to_next_fomc` | int | Calendar days to next FOMC decision. |
| `earnings_prev_session` | list[str] | Mega-cap earnings on the prior session date. |
| `data_day` | bool | A high-relevance release or Fed event is on today's calendar. |
| `high_event_later_today` | bool | A high-relevance event is still ahead in today's session. |
| `next_high_event_time_et` | str | Time of that event (ET). |
| `headlines` | list[headline] | Top RSS titles (records below), newest first. |

## `intraday`

| field | type | description |
|---|---|---|
| `minutes_since_open` | int | Minutes since the cash open. |
| `or_high` | float | Opening range (first 30 min) high (pts). |
| `or_low` | float | Opening range low (pts). |
| `or_complete` | bool | First 30 minutes have elapsed. |
| `spot_vs_or` | enum: above / inside / below | inside / above / below the opening range (once complete). |
| `vwap` | float | Session VWAP (pts), SPY volume as proxy weights. |
| `vwap_method` | str | How VWAP was computed. |
| `spot_minus_vwap_pts` | float | spot - vwap (pts). |
| `rv_today_pct` | float | Realised vol so far today from 5-min returns, annualised (%). |
| `realized_range_em_fraction` | float | Today's range so far / expected_move_day_pts. |
| `high_retested` | bool | Price returned to the session high after a pullback. |
| `low_retested` | bool | Price returned to the session low after a bounce. |
| `vwap_crosses` | int | 5-min closes that crossed the running VWAP so far today. |
| `vwap_crosses_by_cutoff` | int | VWAP crosses up to vwap_cutoff_et (the count the day-type rules use). |
| `vwap_cutoff_et` | str | Cutoff for the VWAP rule (HH:MM ET). |
| `vwap_check_final` | bool | The cutoff has passed, so the VWAP count is final. |
| `vwap_crossed_both_ways` | bool | At least two VWAP crosses by the cutoff. |
| `vwap_above_frac` | float | Share of 5-min closes above VWAP up to the cutoff (0-1). |
| `snapshot_time_et` | str | Classification snapshot time (HH:MM ET); null before it. |
| `snapshot_spot` | float | SPX at the snapshot (pts). |
| `snapshot_vs_or` | enum: above / inside / below | Snapshot spot inside / above / below the opening range. |
| `snapshot_vs_prior_va` | enum: above / inside / below | Snapshot spot above / inside / below the prior value area. |
| `dev_poc` | float | Developing (today's) point of control (pts). |
| `dev_vah` | float | Developing value area high (pts). |
| `dev_val` | float | Developing value area low (pts). |
| `dev_poc_position` | float | Developing POC position in today's range (0 = low, 1 = high). |
| `profile_shape` | enum: D / P / b / elongated | D / P / b / elongated (see concepts/volume-profile). |
| `accepted_outside_dev_va` | enum: above / below / no | above / below when the last acceptance_closes 5-min closes are all beyond that developing value edge; else no. |
| `volume_ratio_recent` | float | Recent 5-min SPY volume / the 12:00-13:30 ET average (volume returning); null before 13:30 ET. |

## `regime`

| field | type | description |
|---|---|---|
| `label` | enum: trend_up / trend_down / balance / gap_and_go / gap_and_fill / undetermined | trend_up / trend_down / balance / gap_and_go / gap_and_fill / undetermined. |
| `lean` | str | Pre-classification lean: gap_up, gap_down, open_above_value, open_below_value, open_inside_value. |
| `rules_fired` | list[str] | Conditions that were met. |
| `rules_failed` | list[str] | Conditions that were not met. |
| `conflicts` | list[str] | Rule sets that point in opposite directions (label becomes undetermined). |
| `prior_label` | str | Label from the earlier post today, if any. |
| `confirmation` | enum: first classification / confirmed / changed | first classification / confirmed / changed against prior_label. |
| `holding` | bool | Whether price now still supports the label. |
| `holding_note` | str | What holding was judged on. |

## `playbook`

| field | type | description |
|---|---|---|
| `live` | enum: early / late / none / pending | early / late / none / pending (pre-market). |
| `direction` | enum: up / down | up / down when the regime gives one. |
| `instrument` | str | single leg, or the high-IV instrument from playbook.yaml. |
| `early_status` | str | Early playbook status and the reason. |
| `early_trigger` | str | Early trigger condition, when live. |
| `early_invalidation` | str | What invalidates the early trigger. |
| `early_window_et` | str | Early window (ET). |
| `early_time_stop_et` | str | Early time stop (ET). |
| `late_status` | str | Late playbook status and the reason. |
| `late_trigger` | str | The one late trigger that qualifies. |
| `late_window_et` | str | Late window (ET). |
| `flat_by_et` | str | Flat-by time (ET). |
| `premium_cap` | str | Late premium cap from playbook.yaml, or not set. |
| `reasons` | list[str] | Why the playbook is in this state. |
| `flip` | list[str] | What would flip the read. |
| `do_not` | list[str] | The never list from playbook.yaml. |

## `data_quality`

| field | type | description |
|---|---|---|
| `null_fields` | list[str] | Fields unexpectedly null for this post type. |
| `fallbacks` | list[str] | Fallbacks used (SPY chain, ES-implied spot, proxy VWAP...). |
| `source_errors` | list[str] | Sources that failed after retries. |
| `notes` | list[str] | Other caveats (early close, empty calendar...). |
| `manual_inputs` | list[str] | Values the user can type in because no free source supplied them. |
| `sources` | list[source] | Sources fetched for this run (records below). |

## record: `event`

| field | type | description |
|---|---|---|
| `date` | str | YYYY-MM-DD. |
| `time_et` | str | HH:MM ET, null if unknown. |
| `name` | str | Description. |
| `category` | str | e.g. CPI, FOMC_DECISION, MEGACAP_EARNINGS, AUCTION_10Y_20Y_30Y, FED_SPEAKER. |
| `premium_relevance` | enum: high / medium / low | high / medium / low (mapping in regime_rules.yaml). |
| `url` | str | Canonical schedule page for the event's source. |

## record: `headline`

| field | type | description |
|---|---|---|
| `title` | str | Headline title only. |
| `source` | str | Feed name. |
| `published_utc` | str | UTC ISO time. |

## record: `level`

| field | type | description |
|---|---|---|
| `name` | str | Level name. |
| `price` | float | Price (pts). |
| `kind` | str | prior / value / overnight / opening_range / vwap / session / developing / round. |
| `confluence` | bool | Another level sits within levels.confluence_tolerance_pts. |
| `confluence_with` | str | Names of those levels. |

## record: `source`

| field | type | description |
|---|---|---|
| `name` | str | Source label. |
| `url` | str | URL fetched (or the page behind a yfinance call). |
| `fetched_at_utc` | str | UTC ISO fetch time. |
| `ok` | bool | False if the fetch failed. |
