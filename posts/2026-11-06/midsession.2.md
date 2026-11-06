---
date: '2026-11-06'
post_type: midsession
version: 2
regime: undetermined
playbook: late
verdict: 'regime classified as undetermined; playbook: late'
watch:
- 'Early: not live, regime is undetermined'
- 'Late: armed, opens 14:30 ET / 11:30 PT'
- ▲ 7444.2 ★ OR high · session high; above it, next is 7450 round
- ▼ 7410.73–7414.18 ★ VWAP · O/N high; below it, next is 7400–7402 ★ dev VAL · round
- 'IV crush -16.9% (VIX1D estimate): not done, needs -20% · VIX1D 23.29 (extreme,
  95th pct of 20 closes)'
- 'Flips the read: gap rules: gap +0.33% is within ±0.5%; balance: developing POC
  7423.5 at 72% of the range (needs 33–67%)'
generated_at: '2026-11-06T17:25:30+00:00'
data_as_of: '2026-11-06T12:25:00-05:00'
schema_version: '2.0'
narrative: claude
model: claude-sonnet-5-5
files:
  raw: data/2026-11-06/midsession.2.raw.json
  brief: data/2026-11-06/midsession.2.brief.json
  llm: data/2026-11-06/midsession.2.llm.json
---

## Verdict

**regime classified as undetermined; playbook: late**

- Early: not live, regime is undetermined
- Late: armed, opens 14:30 ET / 11:30 PT
- ▲ 7444.2 ★ OR high · session high; above it, next is 7450 round
- ▼ 7410.73–7414.18 ★ VWAP · O/N high; below it, next is 7400–7402 ★ dev VAL · round
- IV crush -16.9% (VIX1D estimate): not done, needs -20% · VIX1D 23.29 (extreme, 95th pct of 20 closes)
- Flips the read: gap rules: gap +0.33% is within ±0.5%; balance: developing POC 7423.5 at 72% of the range (needs 33–67%)

No rule set is fully met, so the early playbook is not live. The late playbook is armed from 14:30 ET / 11:30 PT, with a debit spread as the instrument. IV is high and the day's range already stands at 1.41 times the expected move, so watch whether the late trigger fires.

## Technical

**Regime: undetermined** — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart)

- ✓ balance: open 7377.65 inside prior value 7350.35–7470
- ✓ balance: VWAP crossed 2× by 11:00 ET / 08:00 PT (needs ≥ 2)
- ◷ no rule set is fully met
- ✗ gap rules: gap +0.33% is within ±0.5%
- ✗ balance: developing POC 7423.5 at 72% of the range (needs 33–67%)

**Structure:** spot 7415.85 inside the opening range 7369.55–7444.2 · VWAP 7414.18 (4 crosses, spot +1.67) · P-profile, POC 7423.5, value 7402–7431 · range 7369.55–7444.2, spot at 62.02% · 8/11 sectors up — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart) · [sector ETFs](https://finance.yahoo.com/quote/XLK/)

**Premium:** straddle 39.35 @ 7415, 12:25 ET / 09:25 PT = ±39.35 (0.53%) → 7376.5–7455.2 · IV crush -16.9% (VIX1D estimate): not done, needs -20% · 74.18% of ATM extrinsic left ([theta table](../../concepts/premium.html#theta)) — [Yahoo SPX chain](https://finance.yahoo.com/quote/%5ESPX/options) · [Cboe delayed quotes](https://www.cboe.com/delayed_quotes/spx/quote_table)

**Levels** (★ = within 5 pts of each other) — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart) · [ES chart](https://finance.yahoo.com/quote/ES%3DF/chart)

- 7444.2 ★ OR high · session high
- 7431 dev VAH
- 7423.5 dev POC
- **▶ spot 7415.85**
- 7410.73–7414.18 ★ VWAP · O/N high
- 7400–7402 ★ dev VAL · round
- 7379.5 prior POC

**Playbook: late**

- Early (10:00–13:00 ET / 07:00–10:00 PT): not live, regime is undetermined
- Late (14:30–15:45 ET / 11:30–12:45 PT): armed, opens 14:30 ET / 11:30 PT

## News / macro

- 08:30 ET / 05:30 PT · Employment Situation · high (out) ([source](https://www.bls.gov/schedule/news_release/))
- 10:00 ET / 07:00 PT · Prelim UoM Consumer Sentiment · medium (out) ([source](https://www.forexfactory.com/calendar))
- 10:00 ET / 07:00 PT · Prelim UoM Inflation Expectations · medium (out) ([source](https://www.forexfactory.com/calendar))
- 12:15 ET / 09:15 PT · Discussion - Vice Chair for Supervision Michelle W. Bowman · medium (out) ([source](https://www.federalreserve.gov/newsevents/calendar.htm))
- 10y 4.85% (+1.2 bp) · DXY 102.16 (+0.60%) · oil 90.21 (-0.34%) · gold 4069.5 (-1.07%) — [Yahoo](https://finance.yahoo.com/quote/%5ETNX/)
- The S&P 500 could be dangerously exposed to AI. Here are some simple alternatives. (MarketWatch Top Stories)
- The AI ‘credit card’ is getting costlier as CoreWeave bond yield tops 16% (CNBC Markets)
- Federal Reserve Board announces termination of enforcement action with Allegiant United Holdings, LLC, Nano Financial Holdings, Inc., and Nano Banc (Federal Reserve)

**Manual inputs open:** 09:35 ET / 06:35 PT straddle print (Generate page, or python -m digest straddle --set PRICE)

*Missed day? A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.*

**Sources** (fetched 12:25 ET / 09:25 PT): [Yahoo daily bars](https://finance.yahoo.com/quote/%5EGSPC/history) · [Yahoo 5-min bars](https://finance.yahoo.com/quote/%5EGSPC/chart) · [Yahoo SPX chain](https://finance.yahoo.com/quote/%5ESPX/options) · [Cboe daily stats](https://cdn.cboe.com/data/us/options/market_statistics/daily/2026-11-05_daily_options) · [FRED](https://fred.stlouisfed.org/) · [RSS: CNBC Markets](https://www.cnbc.com/id/10000664/device/rss/rss.html) · [RSS: MarketWatch Top Stories](https://feeds.content.dowjones.io/public/rss/mw_topstories) · [RSS: Federal Reserve](https://www.federalreserve.gov/feeds/press_all.xml) · [Fed calendar](https://www.federalreserve.gov/json/calendar.json) · [TreasuryDirect auctions](https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json) · [ForexFactory calendar](https://nfs.faireconomy.media/ff_calendar_thisweek.json) · [Yahoo earnings dates](https://finance.yahoo.com/calendar/earnings)

Dealer gamma / GEX: not computed or estimated (vendor link not set). Concepts: [daily structure](../../concepts/daily-structure.html) · [premium](../../concepts/premium.html) · [volume profile](../../concepts/volume-profile.html) · [edge](../../concepts/edge.html) · [rules](../../concepts/rules.html)
