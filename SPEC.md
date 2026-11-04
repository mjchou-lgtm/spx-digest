# Claude Code prompt — SPX 0DTE Daily Digest, v0

Paste everything below the line into Claude Code at the root of an empty repo.

---

## Context

I trade single-leg 0DTE options on the SPX. I want a web-based, blog-style daily digest that gives me a macro read on the session: what regime we are in, what is on the calendar that could move premiums, whether the day looks trending, choppy, or not worth trading. It is a primer and intra-day update, **not** a signal service. Specific entries and exits are my job.

Build **v0** as described here. Where this spec is silent, choose the simplest thing that works and leave a `TODO` comment. Before writing code, list any questions you have; if none, start.

My environment: Python, VS Code, GitHub. I am in Pacific time; regular session is 06:30–13:00 PT.

## Hard constraints

1. **Free, public data only.** No paid feeds, no brokerage APIs, no scraping behind logins. Delayed (~15 min) data is acceptable for intraday posts.
2. **No risk commentary.** Never mention that 0DTE is risky, suggest position sizing, or add disclaimers about single-leg options. The reader is an experienced trader; risk and sizing are entirely his call. This applies to the Claude-written narrative too — put it in the system prompt.
3. **No trade calls.** No "buy the 5800 call." Regime, levels, catalysts, and what to watch for.
4. **Read-only forever.** Nothing in this codebase should ever place, modify, or cancel an order. Design so that is structurally impossible (no brokerage credentials, no execution modules).
5. **Deterministic indicators, LLM narrative.** All numbers and the regime label come from code. Claude writes prose from a structured brief and may not invent numbers.

## Architecture

- Python 3.11+, `uv` or `pip` with a lockfile.
- **Generation:** scheduled GitHub Actions workflows fetch data → compute indicators → classify regime → call the Claude API for narrative → render a static site → commit and deploy to GitHub Pages.
- **Site:** static HTML via Jinja2 + Markdown (no JS framework). Mobile-first, dark mode, readable on a phone at 05:45. Index page shows today's posts newest-first; archive by date; one page per post. Do not use colour alone to convey meaning (I am colourblind) — pair any colour with a label or icon.
- **Persistence in the repo:**
  - `data/YYYY-MM-DD/<post_type>.raw.json` — every raw fetch, as received.
  - `data/YYYY-MM-DD/<post_type>.brief.json` — the computed indicator brief that was sent to Claude (versioned schema, `schema_version` field).
  - `posts/YYYY-MM-DD/<post_type>.md` — the rendered post with frontmatter.
  - This is the dataset for future indicator work and backtesting; never overwrite a day's files, only add.
- **Secrets** (GitHub Actions secrets): `ANTHROPIC_API_KEY`, `FRED_API_KEY` (free). Nothing else.
- **Local run:** `python -m digest run --post premarket --date 2026-11-03` must work on my laptop with the same secrets in `.env`, and `python -m digest build` must render the site from whatever is in `posts/`. A `--dry-run` flag skips the Claude call and renders the brief as bullet points.

## Schedule (GitHub Actions cron)

Three posts per trading day, Pacific time:

| Post | PT | Purpose |
|---|---|---|
| `premarket` | 05:45 | Overnight, calendar, regime going into the open |
| `midsession` | 09:30 | How the open resolved, regime confirmation or change |
| `afternoon` | 11:45 | Last ~75 min: pin/expansion behaviour, charm/gamma into close, what carried |

Cron is UTC and GitHub does not do DST. Either (a) define two cron entries per post (PST and PDT offsets) and have the script exit early unless the current Pacific time is within the intended window, or (b) run every 15 min during a wide window and let the script decide. Pick (a). Skip NYSE holidays and early closes using `pandas_market_calendars`; on an early-close day, shift `afternoon` to 60 min before the close. Log a one-line skip reason when a run exits early.

## Data sources (all free)

Use `yfinance` as the primary source. Wrap every fetch in a retry with a per-source timeout and record `fetched_at` and `source` in the raw JSON. If a source fails, degrade gracefully: mark the field `null`, note it in the brief, and continue — a post with gaps beats no post.

**Index, futures, volatility**
- `^GSPC` (SPX), `ES=F`, `NQ=F`, `RTY=F` — daily and 5-min bars (overnight range from ES).
- `^VIX`, `^VIX9D`, `^VIX3M`, `^VIX6M` — term structure. `^VVIX`, `^SKEW`.
- `^TNX`, `^FVX`, `^IRX` — rates. `DX-Y.NYB` — dollar. `CL=F`, `GC=F` — oil, gold.
- `SPY`, `RSP` (equal weight), `QQQ`, `IWM`, sector ETFs (`XLK XLF XLE XLV XLY XLP XLI XLU XLRE XLB XLC`) — breadth and leadership proxies.
- Mega-cap drivers: `NVDA AAPL MSFT AMZN GOOGL META TSLA AVGO` — pre-market moves and earnings dates.

**SPX options chain** — `yfinance` `Ticker("^SPX").option_chain(<today's expiry>)`. If `^SPX` chain is unavailable, fall back to `SPY` and scale strikes ×10, and flag the fallback in the post. From the chain compute:
- ATM straddle expected move (points and %), for 0DTE and for the next weekly.
- Put/call ratio by volume and by open interest, 0DTE only.
- Top 5 strikes by call OI and by put OI (likely pin/wall candidates).
- Approximate net gamma exposure by strike (standard GEX approximation: `OI × gamma × 100 × spot² × 0.01`, calls positive, puts negative; compute gamma with Black-Scholes from the chain's implied vol). Report the approximate gamma flip level. Label it "approximate, OI-based" — it is not dealer positioning.

**Volatility statistics**
- CBOE daily put/call ratios (total, index, equity) from the CBOE market-statistics daily CSV.
- Realized volatility: 10-day and 20-day close-to-close on SPX, annualised, vs VIX (variance risk premium read).

**Calendar and catalysts**
- FOMC meeting dates and minutes release dates: commit a `calendars/fomc_2026.json` seeded from federalreserve.gov, with a script to refresh it.
- BLS and BEA release dates (CPI, PPI, NFP, PCE, GDP, retail sales): `calendars/econ_2026.json`, seeded from the official release schedules, with a refresh script. Include scheduled release time in ET.
- Treasury auction schedule (10y/30y/20y in particular): `calendars/auctions.json` from treasurydirect.gov.
- Earnings: `yfinance` calendar for the mega-cap list above plus any S&P 500 name reporting that day with market cap > $200B (maintain a small static list; refresh monthly).
- Fed speakers: scrape the public federalreserve.gov speeches/calendar page; best effort, `null` if it breaks.
- Headlines: RSS only. CNBC Markets, MarketWatch Top Stories, Federal Reserve press releases, BLS news releases. Top 10 titles with timestamps — titles only, no article bodies.
- FRED (`FRED_API_KEY`): `DGS10`, `DGS2`, `T10Y2Y`, `DFF`, `VIXCLS` as a cross-check and for history.

## Indicator brief (what the code computes)

Produce one `brief.json` per post with, at minimum:

- **Levels:** prior-day O/H/L/C, overnight ES high/low and range in SPX points, gap vs prior close (points, %, and as a fraction of expected move), weekly and monthly open, 20-day ATR, average daily range (10-day) and today's range-used so far (intraday posts).
- **Vol:** VIX level and 1-day change, VIX9D/VIX ratio, VIX/VIX3M ratio (contango/backwardation label), VVIX, SKEW, RV10 and RV20 vs VIX, expected move 0DTE and next weekly.
- **Positioning (approx):** 0DTE P/C by volume and OI, top OI strikes, gamma flip estimate, where spot sits relative to it.
- **Cross-asset:** ES, NQ, RTY % moves; 10y yield change; DXY change; oil, gold.
- **Breadth/leadership (proxies):** RSP vs SPY, QQQ vs IWM, sector ranking by % change, mega-cap moves.
- **Calendar:** events today with ET time and a `premium_relevance` flag (`high` for FOMC/CPI/NFP/PCE/mega-cap earnings, `medium` for PPI/retail sales/auctions/Fed speakers, `low` otherwise), events tomorrow, days until next FOMC.
- **Intraday (midsession/afternoon only):** opening-range (first 30 min) high/low and whether price is inside/above/below; VWAP and distance from it; range-used vs ATR; realised vol so far today vs expected move; whether the day's high or low has been retested.

## Regime classification (deterministic)

Implement `digest/regime.py` with explicit, documented rules. Output a label, a confidence (`low/medium/high`), and a list of the rules that fired, so I can audit it. Labels:

- `TREND_UP` / `TREND_DOWN` — e.g. gap > 0.5× expected move holding beyond opening range, breadth confirming, VIX moving opposite price.
- `RANGE` — inside prior-day range, range-used < 50% ATR by midsession, spot near high-OI strike cluster, positive approx gamma.
- `EVENT_WAIT` — `high` relevance event later in the session; premiums elevated vs RV; expect compression then expansion.
- `VOL_EXPANSION` — backwardation (VIX9D > VIX), VVIX spiking, negative approx gamma, range-used > 120% ATR.
- `NO_TRADE` — data quality insufficient, holiday/early close, or conflicting signals with low confidence.

Start with simple thresholds in a config file (`regime_rules.yaml`), not hard-coded numbers. I will tune them. Add a `## Notes` section to the README explaining each rule and the literature it draws on (opening-range, VWAP, gamma/charm into close, vol term-structure, event-day premium behaviour). Cite sources by name; do not fabricate.

## Narrative (Claude API)

- Model: `claude-sonnet-4-5` or newer, via the official `anthropic` Python SDK. One call per post, max ~700 output tokens. Temperature low.
- Input: the `brief.json` plus the previous post of the day (for intraday posts) and yesterday's `afternoon` post (for premarket).
- System prompt must: define the reader as an experienced SPX 0DTE trader; forbid risk/sizing commentary and disclaimers; forbid specific entries/exits; forbid inventing or rounding numbers not in the brief; require the regime label from the brief to be stated as given; ask for plain, direct prose, no hype, no headers beyond the template.
- Output template (Markdown):

```
## Regime: <LABEL> (<confidence>)
One paragraph: what kind of day this looks like and why.

## What matters today
3–6 bullets: catalysts with times, vol structure, positioning context.

## Levels to watch
Bullets: key levels from the brief with the reason each matters.

## What would change the read
2–3 bullets: what would flip the regime label.
```

For `midsession` and `afternoon`, add a first section `## Since the last post` (what resolved vs the prior post's read). For `afternoon`, add `## Into the close` (pin vs expansion, charm/gamma considerations, what to carry into tomorrow's premarket).

- Store the exact prompt and response in `data/YYYY-MM-DD/<post_type>.llm.json`.
- If the API call fails, publish the post with the brief rendered as a table and a banner "Narrative unavailable".

## Site

- `site/` built by `python -m digest build`. Deploy via `actions/deploy-pages`.
- Pages: index (today, three slots, empty slots show "scheduled for HH:MM PT"), post page, archive (calendar-style list by month), a `/data/` page that links the day's JSON files, and an `/about` page that documents the data sources, indicator definitions, and regime rules.
- Post page: narrative first, then a collapsible "Indicator brief" table rendered from `brief.json`, then a "Data quality" footer listing any `null` fields and fallbacks used.
- Frontmatter per post: date, post_type, regime, confidence, generated_at, data_as_of, schema_version.
- Also emit `site/feed.xml` (RSS) and `site/api/latest.json` (the latest brief + regime per post type) — the browser copilot will consume this later.

## Future-proofing (do not build, just leave the seams)

- `digest/strategies/` package with a `Strategy` protocol: `name`, `describe()`, `evaluate(brief) -> StrategyRead` (applicability, conditions met/unmet, what to watch). Ship one trivial example (`OpeningRangeContext`) that only reports whether the opening range has formed and where spot is relative to it. No signals.
- `brief.json` schema should be stable and documented (`docs/brief-schema.md`) because a read-only browser extension will later overlay this data on a brokerage portal. Keep all fields flat or one level deep, snake_case, with units in field names (`expected_move_pts`, `vix_change_pct`).
- `api/latest.json` must be CORS-friendly static JSON.

## Repo layout

```
digest/            # package: fetch/, indicators/, regime.py, narrative.py, build.py, cli.py
digest/strategies/
calendars/
data/
posts/
templates/         # Jinja2
static/            # css
site/              # build output (gitignored, deployed by Actions)
docs/
tests/
.github/workflows/ # premarket.yml, midsession.yml, afternoon.yml, deploy.yml, refresh-calendars.yml (weekly)
regime_rules.yaml
README.md
```

## Tests

- Unit tests for every indicator with fixture data (commit a small `tests/fixtures/` of real yfinance payloads from one past day).
- Regime tests: one fixture brief per label that must produce that label.
- A test that the narrative system prompt contains the forbidden-content rules and that a rendered post contains no words from a `forbidden_phrases.txt` list (e.g. "risky", "disclaimer", "position size", "not financial advice", "buy the", "sell the").
- Schema validation of `brief.json` with `pydantic`.

## Definition of done for v0

1. `python -m digest run --post premarket --dry-run` works locally with no API keys and produces a post.
2. All three workflows run on a schedule, skip non-trading days, and the Pages site updates within 10 minutes of each run.
3. One full trading day of real posts exists in `posts/` and `data/`.
4. README covers setup, secrets, local run, how to tune `regime_rules.yaml`, and the data-source caveats (delays, `^SPX` chain fallback, OI-based GEX approximation).
5. Tests pass in CI.

## Working style

- Work in small commits with clear messages. Open with a short plan and the questions you need answered; then build fetchers first (with fixtures), indicators second, regime third, narrative fourth, site last.
- When a free data source turns out to be unreliable, tell me which and propose the best free alternative rather than silently switching.
- Do not add features outside this spec without asking.
