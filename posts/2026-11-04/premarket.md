---
date: '2026-11-04'
post_type: premarket
version: 1
regime: TREND_UP
confidence: high
generated_at: '2026-11-04T18:41:00+00:00'
data_as_of: '2026-11-04T13:40:00-05:00'
schema_version: '1.0'
narrative: claude
model: claude-sonnet-5-5
files:
  raw: data/2026-11-04/premarket.raw.json
  brief: data/2026-11-04/premarket.brief.json
  llm: data/2026-11-04/premarket.llm.json
---

## Regime: TREND_UP (high)
Spot is 7701.27 against a prior close of 7568.92, with a gap of 66.89 points (0.88%), which is 3.4 times the 0DTE expected move of 19.7 points. All five trend-up rules fired: spot above the prior close, gap at least half the expected move, 9 of 11 sectors up, equal weight keeping pace with SPY (RSP minus SPY at -0.03%), and VIX falling 18.43% to 16.99. The data timestamp is 10:40 PT, so the session has already moved. Range used is 79.76 points, or 103.58% of the 77.0-point ATR20. Much of a normal day's range is already spent.

## What matters today
- Calendar: no events today and none next session (Nov 5). Next FOMC is Dec 9, 35 days out. The driver is the post-midterm repricing, not a scheduled print.
- Vol structure: VIX 16.99, VIX9D 15.91, VIX3M 19.05, in contango. VVIX 92.44, down 13.93%. VIX sits 5.62 points above RV20 (11.37%).
- 0DTE expected move is 19.7 points (0.26%), small relative to the gap and the range already printed. Weekly expected move is 73.1 points, with expiry Nov 6.
- Cross-asset: 10-year yield 4.9% (down 4.8 bp), oil 88.83 (down 7.56%), DXY 101.53, gold up 3.4%. Headlines tie the move to the midterm results and falling oil and yields.
- Leadership is uneven: XLY +4.62%, XLC +3.82%, XLP +3.65%, while XLE is -5.18% and XLI -1.11%. XLK is only +0.28%, with NVDA -1.39% and AVGO -1.5% against AAPL +6.24%, MSFT +6.62% and AMZN +7.1%.
- Approximate OI-based gamma estimate: net GEX at spot is about 26.8 bn, with spot above the approximate flip at 7608.72. This is not dealer positioning.

## Levels to watch
- 7715.57: session high so far, the immediate upside reference.
- 7700: nearest OI strike (spot is 1.27 points away) and a top call OI strike, so a likely pin or magnet area.
- 7635.81: session open and session low, the base of the move.
- 7667.92: overnight high, now well below spot.
- 7610.83: weekly and monthly open, close to the approximate gamma flip at 7608.72.
- 7594.61: prior high. 7568.92: prior close, the gap fill reference.
- 7800 and 7900: next top call OI strikes above. 7400 and 7250: put OI strikes below.

## What would change the read
- Spot giving back the session open at 7635.81 and then heading toward the weekly open at 7610.83 would undercut the gap-and-go structure and push the label toward RANGE.
- A VIX reversal higher, with VVIX rising and contango flattening, would weaken the vol-opposite rule and raise the VOL_EXPANSION score from 0.0.
- Breadth narrowing, with sectors up falling below 8 of 11 or RSP lagging SPY by more than 0.1%, would remove two confirming rules. Oil or yields reversing sharply would be the likely cause.
