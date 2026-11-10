---
date: '2026-11-10'
post_type: midsession
version: 1
regime: balance
playbook: late
verdict: 'Range-bound day (balance); playbook: late, ready from 14:30 ET / 11:30 PT,
  early playbook not live'
meaning: 'In plain terms: buyers and sellers roughly agree on price, so it rotates
  inside a range and moves toward the edges tend to fade.'
watch:
- 'Early setup: not live, it needs an uptrend, downtrend or gap-and-go day and today
  is a range-bound day.'
- 'Late setup: ready, opens 14:30 ET / 11:30 PT.'
- 'Ceiling: 7521.5 (yesterday''s most-traded price). If price holds above it, the
  next level is 7530.03 (top of the first 30 minutes).'
- 'Floor: 7490–7490.65 (bottom of the first 30 minutes + bottom of today''s value
  area). Several levels meet here, which makes it stronger. If price holds below it,
  the next level is 7482.52–7484.19 (overnight low + today''s low).'
- Option prices have deflated 24.3% since the open (an estimate from VIX1D, since
  there is no 09:35 ET / 06:35 PT print), past the 20% mark where the usual deflation
  once the open is out of the way (the IV crush) is treated as finished. Also, the
  1-day volatility gauge (VIX1D) is 13.12, higher than 35% of the last 20 days, so
  options are priced about as usual.
- 'What would change this read: two 5-minute closes in a row outside today''s value
  area (7490–7506).'
generated_at: '2026-11-10T16:32:31+00:00'
data_as_of: '2026-11-10T11:30:00-05:00'
schema_version: '2.1'
narrative: claude
model: claude-sonnet-5-5
files:
  raw: data/2026-11-10/midsession.raw.json
  brief: data/2026-11-10/midsession.brief.json
  llm: data/2026-11-10/midsession.llm.json
---

## Verdict

**Range-bound day (balance); playbook: late, ready from 14:30 ET / 11:30 PT, early playbook not live**

*In plain terms: buyers and sellers roughly agree on price, so it rotates inside a range and moves toward the edges tend to fade.*

What to watch:

- Early setup: not live, it needs an uptrend, downtrend or gap-and-go day and today is a range-bound day.
- Late setup: ready, opens 14:30 ET / 11:30 PT.
- Ceiling: 7521.5 (yesterday's most-traded price). If price holds above it, the next level is 7530.03 (top of the first 30 minutes).
- Floor: 7490–7490.65 (bottom of the first 30 minutes + bottom of today's value area). Several levels meet here, which makes it stronger. If price holds below it, the next level is 7482.52–7484.19 (overnight low + today's low).
- Option prices have deflated 24.3% since the open (an estimate from VIX1D, since there is no 09:35 ET / 06:35 PT print), past the 20% mark where the usual deflation once the open is out of the way (the IV crush) is treated as finished. Also, the 1-day volatility gauge (VIX1D) is 13.12, higher than 35% of the last 20 days, so options are priced about as usual.
- What would change this read: two 5-minute closes in a row outside today's value area (7490–7506).

Price opened inside yesterday's busy zone and has kept crossing today's average price (VWAP). The most-traded price is also in the lower part of the range. That points to a day with no clear direction, even after the inflation report pushed yields up. The early playbook needs a trending day, so it stays off. Next, watch whether price closes twice in a row above 7506 once the late window opens at 14:30 ET / 11:30 PT.

## Technical

**What kind of day: Range-bound day (balance)** — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart)

The checks behind that call (✓ met, ✗ not met):

- ✓ Opened at 7513.09, inside yesterday's value area (7511–7566)
- ✓ Price crossed today's average price (VWAP) 3 times by 11:00 ET / 08:00 PT; a range-bound day crosses it at least 2 times
- ✓ The most-traded price by 11:00 ET / 08:00 PT (7502.5) was 33% of the way up the range; a balanced day has it near the middle (33–67%)
- ✗ Gap day: no real gap. The open was -0.49% from yesterday's close, and a gap day needs more than ±0.5%

**Where price is now:** 7502.74. That is 1.68 points below today's average price (VWAP 7504.42), so sellers have the upper hand right now. It is inside the first 30 minutes' range (7490.65–7530.03): no breakout in either direction. 2 of 11 sectors are up, so the selling is broad. — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart) · [sector ETFs](https://finance.yahoo.com/quote/XLK/)

**Option prices:** An at-the-money straddle (a call plus a put at the current price) costs 32.35 points (quote from 11:32 ET / 08:32 PT). That is the move options are pricing: about ±32.35 points for the rest of today (0.43%), a range of 7470.39–7535.09. Option prices have deflated 24.3% since the open (an estimate from VIX1D, since there is no 09:35 ET / 06:35 PT print), past the 20% mark where the usual deflation once the open is out of the way (the IV crush) is treated as finished. About 82.84% of an at-the-money option's time value is left today ([how it melts through the day](../../concepts/premium.html#theta)). — [Yahoo SPX chain](https://finance.yahoo.com/quote/%5ESPX/options) · [Cboe delayed quotes](https://www.cboe.com/delayed_quotes/spx/quote_table)

**Key levels** — [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart) · [ES chart](https://finance.yahoo.com/quote/ES%3DF/chart)

Prices where the market has turned or traded heavily. ★ marks several within 5 points of each other, which tends to make that area matter more. A value area is the zone that held about 70% of a day's trading.

- 7543.92 today's high
- 7530.03 top of the first 30 minutes
- 7521.5 yesterday's most-traded price
- **▶ price now 7502.74** (sitting at 7500–7511 ★ bottom of yesterday's value area + top of today's value area + today's average price (VWAP) + today's most-traded price + round number)
- 7490–7490.65 ★ bottom of the first 30 minutes + bottom of today's value area
- 7482.52–7484.19 ★ overnight low + today's low
- 7422.24 yesterday's low

**Your playbooks: the late one is live**

- Early (10:00–13:00 ET / 07:00–10:00 PT): not live, it needs an uptrend, downtrend or gap-and-go day and today is a range-bound day
- Late (14:30–15:45 ET / 11:30–12:45 PT): ready, opens 14:30 ET / 11:30 PT

## News / macro

- Today is Tuesday. Only SPX's usual same-day options expire, so no larger expiry is pulling on the afternoon.
- Scheduled releases can move the index and option prices within seconds. High-impact ones matter most:
- 04:00 ET / 01:00 PT: Fed speaker: Speech - Governor Christopher J. Waller (medium impact, already out) ([source](https://www.federalreserve.gov/newsevents/calendar.htm))
- 08:30 ET / 05:30 PT: Consumer inflation (CPI) (high impact, already out) ([source](https://www.bls.gov/schedule/news_release/))
- 13:00 ET / 10:00 PT: 10-Year Note auction (medium impact) ([source](https://www.treasurydirect.gov/auctions/upcoming/))
- 15:30 ET / 12:30 PT: Fed speaker: Speech - Vice Chair for Supervision Michelle W. Bowman (medium impact) ([source](https://www.federalreserve.gov/newsevents/calendar.htm))
- 18:30 ET / 15:30 PT: Fed speaker: Speech - Vice Chair for Supervision Michelle W. Bowman (medium impact) ([source](https://www.federalreserve.gov/newsevents/calendar.htm))
- Big moves elsewhere, which often spill into stocks: the 10-year Treasury yield is up 13 basis points to 4.99%; the dollar index is up 0.69% at 102.35; gold is down 1.97% at 4033.6 ([Yahoo](https://finance.yahoo.com/quote/%5ETNX/))
- Headline: U.S. gas prices fall below $4 for the first time since July (CNBC Markets)
- Headline: Why stocks are falling and 10-year yields are back near 5% after Tuesday’s inflation report (MarketWatch Top Stories)
- Headline: Polymarket says annualized revenue has topped $1.8 billion (CNBC Markets)

**Still needed from you:** the 09:35 ET / 06:35 PT straddle price, to measure how far option prices have deflated (enter it on the Generate page)

*Missed day? A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.*

**Sources** (fetched 11:32 ET / 08:32 PT): [Yahoo daily bars](https://finance.yahoo.com/quote/%5EGSPC/history) · [Yahoo 5-min bars](https://finance.yahoo.com/quote/%5EGSPC/chart) · [Yahoo SPX chain](https://finance.yahoo.com/quote/%5ESPX/options) · [Cboe daily stats](https://cdn.cboe.com/data/us/options/market_statistics/daily/2026-11-09_daily_options) · [FRED](https://fred.stlouisfed.org/) · [RSS: CNBC Markets](https://www.cnbc.com/id/10000664/device/rss/rss.html) · [RSS: MarketWatch Top Stories](https://feeds.content.dowjones.io/public/rss/mw_topstories) · [RSS: Federal Reserve](https://www.federalreserve.gov/feeds/press_all.xml) · [Fed calendar](https://www.federalreserve.gov/json/calendar.json) · [TreasuryDirect auctions](https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json) · [ForexFactory calendar](https://nfs.faireconomy.media/ff_calendar_thisweek.json) · [Yahoo earnings dates](https://finance.yahoo.com/calendar/earnings)

Dealer gamma / GEX: not computed or estimated (vendor link not set).

New to a term? See the [glossary](../../concepts/glossary.html). More background: [daily structure](../../concepts/daily-structure.html) · [premium](../../concepts/premium.html) · [volume profile](../../concepts/volume-profile.html) · [edge](../../concepts/edge.html) · [rules](../../concepts/rules.html)
