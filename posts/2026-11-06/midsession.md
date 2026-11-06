---
date: '2026-11-06'
post_type: midsession
version: 1
regime: balance
playbook: none
verdict: 'regime classified as balance; playbook: none'
generated_at: '2026-11-06T16:39:00+00:00'
data_as_of: '2026-11-06T11:35:00-05:00'
schema_version: '2.0'
narrative: claude
model: claude-sonnet-5-5
files:
  raw: data/2026-11-06/midsession.raw.json
  brief: data/2026-11-06/midsession.brief.json
  llm: data/2026-11-06/midsession.llm.json
---

**VERDICT:** regime classified as balance; playbook: none

**REGIME EVIDENCE**

- balance: open 7377.65 is inside prior value (7350.35–7470)
- balance: VWAP crossed 2 time(s) by 11:00 ET / 08:00 PT (balance needs at least 2)
- balance: developing POC 7401.5 sits at 43% of the day's range (symmetric: 33–67%)
- Not met: gap +0.33% is within ±0.5% (no gap rule)
- ORB: spot 7425.44 is inside the opening range 7369.55–7444.2
- VWAP 7404.25: 2 cross(es) so far; spot is 21.19 pts above
- Profile so far: D-shape, POC 7401.5, value 7392–7424
- Breadth: 6 of 11 sectors up

— [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart) · [sector ETFs](https://finance.yahoo.com/quote/XLK/)

**IV CRUSH:** -12.36% (estimate: VIX1D 20.93 at 09:35 ET / 06:35 PT to 22.27 now, times sqrt(time left); no 09:35 straddle print): not done — [VIX1D](https://finance.yahoo.com/quote/%5EVIX1D/) · [Cboe delayed quotes](https://www.cboe.com/delayed_quotes/spx/quote_table)

**PREMIUM:** ATM straddle 47.8 at the 7425 strike, quoted 11:38 ET / 08:38 PT = ±47.8 pts (0.64% of spot), implied range 7377.64–7473.24 — [Yahoo SPX chain](https://finance.yahoo.com/quote/%5ESPX/options) · [Cboe delayed quotes](https://www.cboe.com/delayed_quotes/spx/quote_table) · VIX1D 22.27 (85th percentile of its last 20 closes: high) — [VIX1D](https://finance.yahoo.com/quote/%5EVIX1D/) · 81.83% of ATM extrinsic left ([theta table](../../concepts/premium.html#theta))

**LEVELS IN PLAY**

- Above: 7444.2 OR high ★ with session high: acceptance above it opens 7450 round 7450
- Below: 7401.5 dev POC ★ with VWAP, round 7400: acceptance below it opens 7392 dev VAL

— [SPX 5-min](https://finance.yahoo.com/quote/%5EGSPC/chart) · [SPY volume](https://finance.yahoo.com/quote/SPY/chart)

**EARLY PLAYBOOK:** not live: high IV on a balance day

High IV on a balance day means sit out, and both the early (10:00–13:00 ET / 07:00–10:00 PT) and late (14:30–15:45 ET / 11:30–12:45 PT) playbooks are not live. Spot is 7425.44, inside the OR (7369.55–7444.2) and inside prior value, with VWAP crossed 2 times by 11:00 ET / 08:00 PT. The developing POC is 7401.5. The straddle implies an expected move of 47.8 points (range 7377.64–7473.24), and the realized range is already 1.28 of that move. The day's range is large but rotational, so it doesn't amount to a trend.

Watch: the flip condition is 2 consecutive 5-min closes beyond either edge of developing value (7392–7424). Spot is already above the upper edge, and the note says it is accepted above developing value, but the regime stays balance until that flip triggers. Flat by 15:45 ET / 12:45 PT if anything changes.

**Manual inputs open**

- 09:35 ET / 06:35 PT ATM straddle print: python -m digest straddle --set PRICE (or the straddle workflow's price input)

*Missed day? A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.*

**Sources**

- [Yahoo Finance daily bars via yfinance (SPX, ES, VIX family, rates, ETFs)](https://finance.yahoo.com/quote/%5EGSPC/history), fetched 11:38 ET / 08:38 PT
- [Yahoo Finance 5-min bars via yfinance (SPX, ES, SPY, VIX, VIX1D)](https://finance.yahoo.com/quote/%5EGSPC/chart), fetched 11:38 ET / 08:38 PT
- [Yahoo Finance SPX option chain via yfinance](https://finance.yahoo.com/quote/%5ESPX/options), fetched 11:38 ET / 08:38 PT
- [Cboe daily market statistics](https://cdn.cboe.com/data/us/options/market_statistics/daily/2026-11-05_daily_options), fetched 11:38 ET / 08:38 PT
- [FRED (St. Louis Fed) series](https://fred.stlouisfed.org/), fetched 11:38 ET / 08:38 PT
- [RSS: CNBC Markets](https://www.cnbc.com/id/10000664/device/rss/rss.html), fetched 11:38 ET / 08:38 PT
- [RSS: MarketWatch Top Stories](https://feeds.content.dowjones.io/public/rss/mw_topstories), fetched 11:38 ET / 08:38 PT
- [RSS: Federal Reserve](https://www.federalreserve.gov/feeds/press_all.xml), fetched 11:38 ET / 08:38 PT
- [Federal Reserve calendar](https://www.federalreserve.gov/json/calendar.json), fetched 11:38 ET / 08:38 PT
- [TreasuryDirect upcoming auctions](https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json), fetched 11:38 ET / 08:38 PT
- [ForexFactory weekly calendar feed](https://nfs.faireconomy.media/ff_calendar_thisweek.json), fetched 11:38 ET / 08:38 PT
- [Yahoo Finance earnings dates via yfinance](https://finance.yahoo.com/calendar/earnings), fetched 11:39 ET / 08:39 PT
- Dealer gamma / GEX: not computed or estimated (vendor link not set)

Concepts: [daily structure](../../concepts/daily-structure.html) · [premium](../../concepts/premium.html) · [volume profile](../../concepts/volume-profile.html) · [edge](../../concepts/edge.html) · [rules](../../concepts/rules.html)
