# SPX 0DTE Daily Digest

A static daily digest for SPX 0DTE day trading, published to GitHub Pages. Each post is a quick-reference card in plain English: a highlighted Verdict section (the verdict, what it means, and the few levels and conditions to watch), then Technical and News / macro sections with source links, and the list of sources fetched. The cards double as a learning tool: terms are replaced or explained where they appear (wording lives in `digest/plain.py`), and every card links to the glossary in `concepts/glossary.md`. Each card also says what is different about the day's calendar (day of the week, weekly, monthly or quarterly options expiry, VIX settlement, month or quarter end, early close, and high-impact releases still ahead), computed in `digest/indicators/daycal.py` from the NYSE session calendar; positioning itself (open interest, dealer gamma) is not measured. Three cards per trading day:

| Post | ET / PT | Card |
|---|---|---|
| `premarket` | 09:15 / 06:15 | Events, overnight gap and range, vol, expected move, level stack, plan |
| `midsession` | 10:45 / 07:45 (skipped on early-close days) | Regime as classified at 10:30 ET, the evidence, IV crush, levels in play, early playbook |
| `afternoon` | 14:15 / 11:15 (60 min before an early close) | Regime confirmed or changed, range so far, the late trigger, theta now, the do-not list |

The trading style it serves: single-leg, defined-risk SPX 0DTE, flat by 15:45 ET, trading the regime and not a view. Two playbooks are kept separate: **early** (10:00–13:00 ET, off the opening range after IV crush) and **late** (14:30–15:45 ET, on an objective trigger, premium-capped). Their settings are in `playbook.yaml`.

Every number, the regime label and the playbook status come from code (`digest/indicators`, `digest/regime.py`, `digest/playbook.py`). Claude writes only the VERDICT line and a narrative of at most 80 words from those fields, in plain English. Free data only: where no free source has a value, the card shows a manual-input field and a link instead of a number. Dealer gamma / GEX is not computed or estimated; `DIGEST_GEX_VENDOR_URL` is a link slot for a vendor page.

**Read-only by construction.** There are no brokerage clients, order models or execution modules, and the only secrets are `ANTHROPIC_API_KEY` and `FRED_API_KEY`. `tests/test_pipeline.py::test_codebase_has_no_execution_paths` fails if a broker SDK import or order function is added. The journal is a CSV you fill in by hand.

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
| `ANTHROPIC_API_KEY` | GitHub Actions secret / `.env` | The verdict line and narrative (one call per post). Without it the card publishes with the computed verdict, no narrative, and a "Narrative unavailable" line. |
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
python -m digest run --post midsession --date 2026-11-05 --dry-run   # replay a past session as of the slot time
python -m digest run --post premarket                    # real run into posts/ + data/ (uses .env)
python -m digest straddle                                # capture today's ATM straddle from the free chain now
python -m digest straddle --set 58.40                    # or type the 09:35 ET print in by hand
python -m digest journal                                 # expectancy by playbook and entry window
python -m digest build                                   # render site/ from posts/
python -m digest refresh-calendars --year 2026
python -m pytest -q
```

- `--dry-run` skips the Claude call, uses the computed verdict, and writes to the gitignored `out/` folder so test posts never enter the dataset. Add `--write` to write into `posts/` and `data/` instead.
- `--date` with a past date replays the session as of that post's slot time. yfinance has no historical option chains, so the straddle and expected move are null in replays, and the IV-crush check falls back to the VIX1D estimate.
- `--scheduled` is the cron mode: it exits with a one-line skip reason unless the current Pacific time is within −5/+40 minutes of the slot, and skips if that post already exists today.
- On a non-trading day the run uses only sources that don't need an open market. The regime is `undetermined`. If there is nothing to discuss, it asks for confirmation (local) or needs `--confirm-empty` (the workflow's `confirm_empty` input).

### The 09:35 ET straddle print

The IV-crush check compares the ATM straddle now with its 09:35 ET print (crush done at −20% or lower). The print is stored in `data/YYYY-MM-DD/straddle_0935.json`:

- `straddle.yml` captures it from the free Yahoo chain between 09:35 and 10:00 ET when its scheduled run is on time.
- You can type it in: the form on the site's Generate page, the `straddle` workflow's `price` input, or `python -m digest straddle --set PRICE`. A manual entry takes precedence.
- With no print for the day, the card shows an **estimate** from VIX1D × √(time left), labelled as an estimate, and lists the print under "Manual inputs open". Set `early.allow_vix1d_crush_estimate: false` in `playbook.yaml` to turn the estimate off.

### Journal

`journal/trades.csv` has one row per trade, filled in by hand (columns in `journal/README.md`). `python -m digest journal` prints expectancy by playbook and by entry window once a playbook has 30 rows.

### Files (append-only dataset)

```
data/YYYY-MM-DD/<post>.raw.json     every fetch as received, with source / fetched_at / error per source
data/YYYY-MM-DD/<post>.brief.json   the computed fields sent to Claude (schema 2.0: docs/brief-schema.md)
data/YYYY-MM-DD/straddle_0935.json  the 09:35 ET straddle print (auto or manual)
data/YYYY-MM-DD/<post>.llm.json     exact request (system + user) and response, validation results
posts/YYYY-MM-DD/<post>.md          the post with frontmatter
```

Files are never overwritten (exclusive create). Posts from before schema 2.0 (2026-11-04) stay in the archive as written. A re-run of the same post writes `premarket.2.*`, `premarket.3.*`, and the site shows the newest version with links to the earlier ones. Scheduled runs never add versions. Only manual runs do.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `premarket.yml`, `midsession.yml`, `afternoon.yml` | cron (one entry per DST offset) + **manual** | generate → commit `posts/`, `data/` → deploy |
| `straddle.yml` | cron 09:35 ET (one entry per DST offset) + **manual** (optional `price`) | record the 09:35 ET straddle print → commit `data/` |
| `_post.yml` | called by the three post workflows | the shared generate/commit/deploy job (reusable workflows can't be run by hand) |
| `deploy.yml` | after each post, on pushes to site code + **manual** | `python -m digest build` → GitHub Pages |
| `refresh-calendars.yml` | Mondays 11:00 UTC + **manual** | refresh `calendars/*.json`, commit if changed |
| `ci.yml` | push / PR + **manual** | `pytest` |

**Manual runs** (Actions → *workflow* → Run workflow) of a post workflow take these inputs:
- `force` (default on): run now, ignoring the time window.
- `date`: replay a past date.
- `dry_run`: no Claude call, nothing committed, output uploaded as an artifact.
- `confirm_empty`: publish on a non-trading day even if there's nothing to discuss.

**Cron and DST.** GitHub cron is UTC and ignores DST, so each post has a PDT entry and a PST entry, and the script skips the one that is an hour off. `afternoon.yml` also has 09:00 PT entries that only do something on NYSE early-close days. The window allows a run to start up to 40 minutes late. Holidays and early closes come from `pandas_market_calendars` (NYSE).

**GitHub's scheduler does not run this repo's crons on time.** Every scheduled run from 2026-11-04 to 11-09 started 3–10 hours after its cron time (for example the 13:15 UTC premarket cron ran at 22:58 UTC on 11-09, and even the Monday 11:00 UTC calendar refresh ran at 21:22 UTC), so all of them skipped with a window message and nothing was posted. Nothing in the repo causes this: GitHub documents that scheduled runs can be delayed under load, and in practice low-activity repositories get the worst of it. Manual runs start within seconds, so the reliable path is to **trigger `workflow_dispatch` from an outside clock** at the slot times:

1. Create a fine-grained token (Settings → Developer settings → Fine-grained tokens): only this repository, permission **Actions: Read and write**, nothing else, with an expiry.
2. Put a job on any scheduler that can send an HTTP request at a fixed time of day in the `America/Los_Angeles` time zone (a hosted cron service, a Cloudflare Worker cron trigger, or a machine of your own that is awake), one per slot on weekdays: `06:15` premarket, `06:35` straddle, `07:45` midsession, `11:15` afternoon, plus `09:00` afternoon for early-close days. Each job is the request below, or `scripts/dispatch.sh <post>` where a shell is available.
3. The workflow keeps its own checks (`force=false`: same time window, trading-day and early-close rules, one post per slot), so a job that fires on a holiday or at the wrong time simply skips.

```
POST https://api.github.com/repos/mjchou-lgtm/spx-digest/actions/workflows/premarket.yml/dispatches
Accept: application/vnd.github+json
Authorization: Bearer <token>
X-GitHub-Api-Version: 2022-11-28

{"ref":"main","inputs":{"force":"false"}}
```

(`straddle.yml` takes `{"ref":"main","inputs":{}}`.) Until that is set up, the Generate page on the site (or Actions → Run workflow) posts on demand.

On early-close days there is **no `midsession` post**: the scheduled run skips with a one-line reason, and the afternoon post builds on the premarket post instead. A manual run with `force` can still produce one.

All writers share the concurrency group `digest-writer`, so commits don't race, and pushes retry with `pull --rebase`.

## Tuning the rules

**`regime_rules.yaml`** holds every threshold of the day-type classifier; `digest/regime.py` only says what is compared.

| Label | Rule |
|---|---|
| `gap_and_go` | \|gap\| > `gap_pct_min` (0.5%) and at `classify_time_et` (10:30) spot is beyond the opening range in the gap direction |
| `gap_and_fill` | \|gap\| > `gap_pct_min` and at 10:30 spot is back inside the prior value area |
| `trend_up` / `trend_down` | opens outside the prior value area, at most `trend_max_vwap_crosses` (1) VWAP crosses by `vwap_cutoff_et` (11:00), and at least `one_sided_min_frac` (70%) of 5-minute closes on that side of VWAP |
| `balance` | opens inside the prior value area, at least `balance_min_vwap_crosses` (2) VWAP crosses by the cutoff, most-traded price as of the cutoff between `profile_lower` and `profile_upper` of the range |
| `undetermined` | before 10:30 ET, when no rule set is fully met, or when the gap rule and the structure rule point in opposite directions |

Gap rules are checked first. The mid-session card runs at 10:45 ET, before the 11:00 VWAP cutoff, so its label is marked provisional; the afternoon card uses the final count. Both the VWAP count and the profile check stop at the cutoff, so the label does not drift later in the day. Each brief records `regime.rules_fired` and `regime.rules_failed`, so a label can be audited from `brief.json`. To re-label history after a change, rebuild briefs from the stored raw payloads with `digest.pipeline.build_brief(raw)`; it is pure and needs no network.

Also in this file: `levels.confluence_tolerance_pts` and `round_step_pts` for the level stack, the `premium` thresholds (crush, VIX1D percentile bands, volume-returning ratio, theta table times), and `premium_relevance` for calendar events.

**`playbook.yaml`** holds the two playbooks: windows, which regimes make the early playbook live, the IV-crush requirement, the high-IV rules, the never list, and the fields that are yours to set (`sizing`, `stop`, `target`, `max_trades`, `premium_cap`). Unset fields show as "not set" on the cards and on the site's rules page; the digest never fills them in.

Checked on real data: 2026-11-05 classifies as `trend_down` and 2026-11-06 as `balance`. 2026-11-04 classifies as `undetermined`: it gapped +0.89% and opened above the prior value area, was inside the opening range at 10:30, and crossed VWAP three times by 11:00, so neither gap rule, nor trend, nor balance (which needs an open inside prior value) is met.

## Data sources and caveats

- **yfinance** is the primary source: unofficial, rate-limited, and sometimes missing tickers. Index and ETF data can be delayed up to ~15 minutes. Every fetch retries and then degrades to `null`; the field goes into the post's *Data quality* footer and the post still publishes.
- **Value area, POC, VWAP:** volume-at-price from 5-minute bars in 1-point bins with a 70% value area. SPX has no volume, so each SPX bar is weighted by SPY 5-minute volume. This is coarser than a tick-based futures profile and can differ from it by a few points.
- **SPX option chain:** `^SPX` from yfinance for today's expiry and the next Friday weekly. If it fails, the SPY chain is used with strikes and points ×10, and the post says so. Before the open the chain shows stale quotes; the 09:35 ET print is the reference for the day.
- **VIX1D** comes from Yahoo (`^VIX1D`). Its percentile is the rank of the current value against its last 20 closes; labels: low below 25, high from 75, extreme from 95.
- **Term structure** is VIX / VIX3M from Yahoo, with a link to vixcentral for the futures curve (not scraped).
- **Theta reference** is a square-root-of-time model; it assumes implied vol does not change.
- **Economic calendar:** FOMC from federalreserve.gov, GDP/PCE from BEA, CPI/PPI/NFP/retail sales from FRED's release calendar (BLS blocks automated clients, and that is not worked around). ForexFactory's public weekly JSON feed adds releases those don't cover (ISM, claims, sentiment); it rate-limits, so it is fetched once per post and a failure only drops those extra rows. Each event links to its canonical schedule page.
- **Pre-market spot** is ES last minus the ES–SPX basis at the prior cash close. The overnight range uses the same basis.
- **Fed speakers** come from federalreserve.gov's calendar JSON, best effort. **Earnings** from yfinance are dates only. "Mega-cap earnings last night" comes from the prior session's stored brief when there is one.
- **Sources list:** every card ends with the URLs fetched for that run and the fetch time. For yfinance calls the link is the Yahoo page behind the data.
- **Narrative guardrails:** Claude's output must start with `VERDICT:`, the verdict must contain the computed regime label and playbook status, the narrative is capped at 80 words, and nothing in `forbidden_phrases.txt` may appear. Otherwise the card publishes with the computed verdict and no narrative. Numbers that aren't in the fields are logged as warnings in `llm.json`. The model is `claude-sonnet-5-5` at low effort.

## Notes

Where the rules come from. These are heuristics for reading a session, with thresholds to tune.

**Opening range.** The first 30 minutes set a reference range; a hold beyond it suggests directional conviction, rotation inside it suggests balance. See Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990), and Gao, Han, Li and Zhou, "Market Intraday Momentum" (*Journal of Financial Economics*, 2018).

**Value area and day types.** POC, value area and the open's position against prior value come from Market Profile (J. Peter Steidlmayer, CBOT) and Dalton, Jones and Dalton, *Mind Over Markets* (1990), which also describes trend and balance (non-trend) days.

**VWAP.** The standard execution benchmark (Berkowitz, Logue and Noser, "The Total Cost of Transactions on the NYSE," *Journal of Finance*, 1988). Sustained trade on one side suggests one-sided flow; repeated crossing suggests balance.

**Expected move.** The ATM straddle is a standard quick estimate of the expected move, about 0.8 σ√T (Brenner and Subrahmanyam, "A Simple Formula to Compute the Implied Standard Deviation," *Financial Analysts Journal*, 1988). The same √T scaling is behind the theta reference.

**Implied vol around the open and events.** Implied vol builds into scheduled uncertainty and falls once it resolves (Ederington and Lee, "The Creation and Resolution of Market Uncertainty," *JFQA*, 1996). That is the IV-crush check.

**0DTE specifically.** Dim, Eraker and Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation" (SSRN, 2024).

## Repo layout

```
digest/            fetch/, indicators/, regime.py, playbook.py, narrative.py, pipeline.py, render.py, build.py, cli.py, journal.py, storage.py, schedule.py, calendars.py
regime_rules.yaml  day-type thresholds          playbook.yaml  the two playbooks (your rules)
concepts/          explainer pages (Markdown), linked from every post
journal/           trades.csv (filled in by hand) + README
digest/strategies/ Strategy protocol + OpeningRangeContext (context only, no signals)
calendars/         fomc_2026.json, econ_2026.json, auctions.json, large_caps.json
data/ posts/       the append-only dataset
templates/ static/ site templates and CSS
docs/              brief-schema.md (generated: python -m digest.schema_doc)
tests/             unit tests; tests/fixtures holds real payloads for 2026-11-05 (trend_down) and 2026-11-06 (balance)
```
