# SPX 0DTE Daily Digest

A static, blog-style daily digest for SPX 0DTE trading: what regime the session is in, which catalysts could move premiums, and the levels that matter. Three posts per trading day (Pacific time):

| Post | PT | Purpose |
|---|---|---|
| `premarket` | 05:45 | Overnight, calendar, regime going into the open |
| `midsession` | 09:30 (skipped on early-close days) | How the open resolved; regime confirmation or change |
| `afternoon` | 11:45 (60 min before an early close) | Pin vs expansion, gamma/charm into the close, what carried |

It is a primer, not a signal service. All numbers and the regime label come from code (`digest/indicators`, `digest/regime.py`); Claude only writes prose from the computed brief.

**Read-only by construction.** There are no brokerage clients, order models or execution modules, and the only secrets are `ANTHROPIC_API_KEY` and `FRED_API_KEY`. `tests/test_pipeline.py::test_codebase_has_no_execution_paths` fails if a broker SDK import or order function is added.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock     # pinned; pyproject.toml lists the direct deps
cp .env.example .env                           # optional for dry runs
```

Python 3.11+ (CI uses 3.14, matching the lockfile). To change dependencies, edit `pyproject.toml`, install, and regenerate the lock with `pip freeze --exclude-editable > requirements.lock`.

### Secrets

| Name | Where | Used for |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub Actions secret / `.env` | The narrative (one call per post). Without it the post publishes with the brief as a table and a "Narrative unavailable" banner. |
| `FRED_API_KEY` | GitHub Actions secret / `.env` | Rates cross-check (DGS10, DGS2, T10Y2Y, DFF, VIXCLS) and the BLS/Census release dates in `calendars/econ_YYYY.json`. Free at fred.stlouisfed.org. |

Nothing else is needed.

### GitHub setup (once)

1. **Settings → Pages → Source: GitHub Actions.**
2. **Actions → refresh-calendars → Run workflow.** The committed `calendars/econ_2026.json` only holds BEA releases (GDP, PCE). CPI, PPI, NFP and retail-sales dates come from FRED and need the secret, so this first run fills them in. After that it runs weekly.
3. Optional: **Actions → premarket → Run workflow** to publish a first post.

## Local run

```bash
python -m digest run --post premarket --dry-run          # no API keys needed; writes to out/
python -m digest build --root out --out out/site         # preview dry-run output
python -m digest run --post premarket --date 2026-11-03  # real run into posts/ + data/ (uses .env)
python -m digest build                                   # render site/ from posts/
python -m digest refresh-calendars --year 2026
python -m pytest -q
```

- `--dry-run` skips the Claude call, renders the brief as bullet points, and writes to the gitignored `out/` folder so test posts never enter the dataset. Add `--write` to write into `posts/` and `data/` instead.
- `--date` with a past date replays the session as of that post's slot time. yfinance has no historical option chains, so expected move, P/C and GEX are null in replays. Daily values for tickers without 5-minute bars use that day's close (`TODO` in `indicators/__init__.py`).
- `--scheduled` is the cron mode: it exits with a one-line skip reason unless the current Pacific time is within −5/+40 minutes of the slot, and skips if that post already exists today.
- On a non-trading day the run uses only sources that don't need an open market: next session's calendar, headlines, futures if trading, and FRED. The regime is `NO_TRADE`. If there is nothing to discuss, it asks for confirmation (local) or needs `--confirm-empty` (the workflow's `confirm_empty` input).

### Files (append-only dataset)

```
data/YYYY-MM-DD/<post>.raw.json     every fetch as received, with source / fetched_at / error per source
data/YYYY-MM-DD/<post>.brief.json   the computed brief sent to Claude (schema: docs/brief-schema.md)
data/YYYY-MM-DD/<post>.llm.json     exact request (system + user) and response, validation results
posts/YYYY-MM-DD/<post>.md          the post with frontmatter
```

Files are never overwritten (exclusive create). A re-run of the same post writes `premarket.2.*`, `premarket.3.*`, and the site shows the newest version with links to the earlier ones. Scheduled runs never add versions. Only manual runs do.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `premarket.yml`, `midsession.yml`, `afternoon.yml` | cron (one entry per DST offset) + **manual** | generate → commit `posts/`, `data/` → deploy |
| `_post.yml` | called by the three above | the shared generate/commit/deploy job (reusable workflows can't be run by hand) |
| `deploy.yml` | after each post, on pushes to site code + **manual** | `python -m digest build` → GitHub Pages |
| `refresh-calendars.yml` | Mondays 11:00 UTC + **manual** | refresh `calendars/*.json`, commit if changed |
| `ci.yml` | push / PR + **manual** | `pytest` |

**Manual runs** (Actions → *workflow* → Run workflow) of a post workflow take these inputs:
- `force` (default on): run now, ignoring the time window.
- `date`: replay a past date.
- `dry_run`: no Claude call, nothing committed, output uploaded as an artifact.
- `confirm_empty`: publish on a non-trading day even if there's nothing to discuss.

**Cron and DST.** GitHub cron is UTC and ignores DST, so each post has a PDT entry and a PST entry, and the script skips the one that is an hour off. `afternoon.yml` also has 09:00 PT entries that only do something on NYSE early-close days. GitHub often starts scheduled runs 5–30 minutes late, so the window allows up to 40 minutes. Holidays and early closes come from `pandas_market_calendars` (NYSE).

On early-close days there is **no `midsession` post**: the scheduled run skips with a one-line reason, and the afternoon post builds on the premarket post instead. A manual run with `force` can still produce one.

All writers share the concurrency group `digest-writer`, so commits don't race, and pushes retry with `pull --rebase`.

## Tuning `regime_rules.yaml`

All thresholds and weights live in `regime_rules.yaml`. `digest/regime.py` only defines what each named condition compares.

- **Per label:** `conditions.<name>.weight` sets importance (0 = gate only), and `params` sets thresholds. `required` lists conditions that must be true. `min_evaluable_weight` stops a label from winning on one condition when the rest are null.
- **Score** = weight of conditions met ÷ weight of conditions evaluable. Conditions with null inputs are skipped, for example opening-range rules before the open.
- **Global:** `min_score` (below this → `NO_TRADE`), `conflict_margin` (top two this close at low confidence → `NO_TRADE`), and the `confidence` bands.
- **Gates:** `critical_fields` (any null → `NO_TRADE`), `important_fields` with `max_important_missing`, and `early_close_confidence_penalty`.
- `premium_relevance` maps calendar categories to high/medium/low.

Every post records `regime.rules_fired` and `regime.scores`, so you can audit a label from `brief.json`. To re-score history after a change, rebuild briefs from the stored raw payloads with `digest.pipeline.build_brief(raw)`. It's pure and needs no network. `tests/test_regime.py` holds one fixture brief per label. Update the fixtures when you change a threshold on purpose.

## Data sources and caveats

- **yfinance** is the primary source: unofficial, rate-limited, and sometimes missing tickers. Index and ETF data can be delayed up to ~15 minutes. Every fetch retries 3 times and then degrades to `null`. The field goes into the post's *Data quality* footer, and the post still publishes.
- **SPX option chain:** `^SPX` from yfinance for today's expiry and the next Friday weekly. If it fails, the SPY chain is used with strikes and points ×10, and the post says so. Pre-market the chain shows the prior session's quotes. When there's no bid/ask, the straddle uses last prices.
- **Expected move** is the ATM straddle. Intraday the 0DTE straddle only prices the rest of the session, so gap and range ratios use the morning's premarket straddle (`vol.expected_move_day_pts`). Without a premarket brief, the current straddle is scaled by √time, and the post flags it.
- **GEX is approximate and OI-based:** per strike `OI × BS gamma × 100 × spot² × 0.01`, calls positive and puts negative, using the 0DTE chain only. It assumes customers are long puts and short calls against dealers, which is a convention, **not dealer positioning**. OI is as of the prior close, so same-day 0DTE flow isn't in it. The "gamma flip" is where the summed profile crosses zero within ±5% of spot.
- **VWAP:** SPX has no volume, so SPX typical price is weighted by SPY 5-minute volume.
- **Pre-market spot** is ES last minus the ES–SPX basis at the prior cash close. The overnight range uses the same basis.
- **CBOE put/call:** the legacy CBOE CSV downloads were retired, so this uses the JSON behind cboe.com's daily market statistics page (prior session).
- **BLS** blocks automated clients (403). The BLS news RSS feed is dropped, and CPI/PPI/NFP dates come from FRED's release calendar. Each FRED release id is checked against its name before use.
- **Fed speakers** come from federalreserve.gov's calendar JSON, best effort. **Earnings** from yfinance are dates only, with no before/after-the-bell timing.
- **Headlines:** RSS titles only (CNBC Markets, MarketWatch Top Stories, Federal Reserve press releases), round-robin across feeds.
- **Narrative guardrails:** the response must follow the template and state the brief's regime label verbatim, and it can't contain anything in `forbidden_phrases.txt`. Otherwise the post falls back to the table. Numbers in the prose that aren't in the brief are logged as warnings in `llm.json`. The model is `claude-sonnet-5-5` at low effort. It rejects a non-default `temperature`, so terseness comes from effort and the prompt. Server-side refusal fallback is enabled.

## Notes

How each rule is meant to work, and the literature behind it. These are heuristics for the session, not tested strategies. Thresholds are starting points to tune.

**Opening range (TREND `holds_beyond_or`, RANGE).** The first 30 minutes set a reference range. A hold beyond it suggests directional conviction, and rotation inside it suggests balance. Opening-range breakout ideas go back to Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990). Zarattini and Aziz study ORB on US equities/ETFs in "Can Day Trading Really Be Profitable?" (SSRN, 2023). Gao, Han, Li and Zhou, "Market Intraday Momentum" (*Journal of Financial Economics*, 2018), find that the first half-hour's return predicts the last half-hour's. That's why the opening read carries into the afternoon post.

**Gap vs expected move (TREND `gap_vs_em`, RANGE `small_gap`).** A gap is scaled by what options priced for the day rather than by points. The ATM straddle is a standard quick estimate of the expected move, about 0.8 σ√T. See Brenner and Subrahmanyam, "A Simple Formula to Compute the Implied Standard Deviation" (*Financial Analysts Journal*, 1988). The 20-day ATR (Wilder, *New Concepts in Technical Trading Systems*, 1978) scales range-used.

**VWAP (TREND `above/below_vwap`, RANGE `near_vwap`).** VWAP is the standard execution benchmark (Berkowitz, Logue and Noser, "The Total Cost of Transactions on the NYSE," *Journal of Finance*, 1988). Sustained trade away from it on one side suggests one-sided flow, and oscillation around it suggests balance.

**Breadth and equal weight (TREND `breadth_confirms`, `equal_weight_confirms`).** An index move confirmed by most sectors, and by RSP keeping pace with SPY, is less likely to be a handful of mega-caps. This is a heuristic, with no single canonical paper.

**VIX opposite price (TREND `vix_opposite`).** Equity returns and implied-vol changes are strongly negatively correlated (the leverage/volatility-feedback effect; Black, "Studies of Stock Price Volatility Changes," 1976). A trend day with VIX falling (up) or rising (down) is the normal pattern. A divergence weakens the read.

**Gamma and pinning (RANGE `positive_gamma`, `near_oi_cluster`; VOL_EXPANSION `negative_gamma`).** When hedgers are net long gamma they trade against moves, which damps volatility and can pin price near high-OI strikes. Net short gamma does the opposite. See Avellaneda and Lipkin, "A Market-Induced Mechanism for Stock Pinning" (*Quantitative Finance*, 2003), Ni, Pearson and Poteshman, "Stock Price Clustering on Option Expiration Dates" (*JFE*, 2005), and Ni, Pearson, Poteshman and White, "Does Option Trading Have a Pervasive Impact on Underlying Stock Prices?" (*Review of Financial Studies*, 2021). Baltussen, Da, Lammers and Martens, "Hedging Demand and Market Intraday Momentum" (*JFE*, 2021), connect hedging of negative gamma to late-day momentum. For 0DTE specifically, see Dim, Eraker and Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation" (SSRN, 2024). The public GEX approximation used here follows SqueezeMetrics' "Gamma Exposure" white paper (2017). Its sign convention is an assumption, which is why it's labelled approximate.

**Charm into the close (afternoon post).** As expiry approaches, a 0DTE option's delta moves quickly toward 0 or 1 even when price doesn't move. That's charm, the time derivative of delta in Black-Scholes; see Hull, *Options, Futures, and Other Derivatives*. Hedges of large OI near spot get adjusted late in the day, which is the mechanism behind pin vs expansion into the close. The digest gives the context (OI walls, approximate gamma sign, range used) and doesn't model charm flows.

**Vol term structure (VOL_EXPANSION `front_backwardation`, `term_backwardation`, `vvix_spike`).** VIX futures and VIX-tenor indices are usually in contango. Backwardation (VIX9D > VIX, or VIX > VIX3M) marks stress, when near-term uncertainty is priced above longer-term. See Johnson, "Risk Premia and the VIX Term Structure" (*Journal of Financial and Quantitative Analysis*, 2017). A VVIX spike is vol-of-vol being bid.

**Variance risk premium (EVENT_WAIT `premium_rich_vs_rv`, `em_rich_vs_rv`).** Implied vol usually sits above subsequent realised vol. See Carr and Wu, "Variance Risk Premiums" (*RFS*, 2009), and Bollerslev, Tauchen and Zhou, "Expected Stock Returns and Variance Risk Premia" (*RFS*, 2009). An unusually large gap ahead of a scheduled release means the event is priced in.

**Event-day behaviour (EVENT_WAIT `high_event_later`, `compressed_so_far`).** Implied vol builds into scheduled announcements and falls after them. See Ederington and Lee, "The Creation and Resolution of Market Uncertainty: The Impact of Information Releases on Implied Volatility" (*JFQA*, 1996), and Beber and Brandt, "The Effect of Macroeconomic News on Beliefs and Preferences: Evidence from the Options Market" (*Journal of Monetary Economics*, 2006). Price tends to compress before the release and expand after. For FOMC days, Lucca and Moench, "The Pre-FOMC Announcement Drift" (*Journal of Finance*, 2015), and Savor and Wilson, "How Much Do Investors Care About Macroeconomic Risk?" (*JFQA*, 2013), document distinctive returns around scheduled announcements.

**NO_TRADE.** This label means the data can't support a read: critical fields are missing, too many important fields are null, the market is closed, or the top two labels are too close at low confidence. It isn't a market call.

## Repo layout

```
digest/            fetch/, indicators/, regime.py, narrative.py, pipeline.py, render.py, build.py, cli.py, storage.py, schedule.py, calendars.py
digest/strategies/ Strategy protocol + OpeningRangeContext (context only, no signals)
calendars/         fomc_2026.json, econ_2026.json, auctions.json, large_caps.json
data/ posts/       the append-only dataset
templates/ static/ site templates and CSS
docs/              brief-schema.md (generated: python -m digest.schema_doc)
tests/             unit tests; tests/fixtures holds a real 2026-11-04 payload and one brief per regime label
```
