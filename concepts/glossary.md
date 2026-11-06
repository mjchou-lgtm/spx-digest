# Glossary: the terms on the cards, in plain English

Each entry says what the thing is and why a card mentions it.

## Price and levels

**Key level.** A price where the market has turned before or traded heavily. Price often pauses, bounces or speeds up there, so levels are where to pay attention.

**Ceiling / floor.** The nearest key level above and below the current price. Not a prediction that price stops there; it is where the next decision gets made.

**Stacked levels (★).** Several key levels within a few points of each other. More traders are watching the same area for different reasons, so it tends to matter more.

**First 30 minutes' range (opening range).** The high and low between 09:30 and 10:00 ET. A move that holds beyond it suggests one side has taken control; staying inside it suggests nobody has.

**Gap.** The difference between today's open and yesterday's close. The cards treat more than 0.5% as a real gap. A gap either keeps going (gap-and-go) or gets given back (gap-and-fill), and the first hour shows which.

**VWAP (today's average price).** The average price paid today, weighted by how much traded at each price. Above it, the average buyer today is in profit; below it, the average buyer is losing. Price staying on one side all morning is a sign of a trend. Price crossing back and forth is a sign of a range.

**Value area.** The price zone that held about 70% of a day's trading. It is where the market agreed on price. "Yesterday's value area" is the reference for today's open: opening inside it means nothing has changed much; opening outside it means the market is rejecting yesterday's prices.

**Most-traded price (point of control, POC).** The single price with the most trading that day. It acts like a magnet in a range-bound market.

**A 5-minute close.** Where price finishes a 5-minute bar. The cards ask for two closes in a row beyond a level before calling it a real break, because a brief poke through a level often reverses.

## Kinds of day

**Uptrend / downtrend day.** One side is in control from early on. Price holds one side of its average and pullbacks are shallow.

**Range-bound day (balance).** Buyers and sellers agree on price. It rotates inside a range, and moves toward the edges tend to fade.

**Gap-and-go.** The market opens with a jump and keeps going the same way.

**Gap-and-fill.** The market opens with a jump and then returns to yesterday's prices.

**No clear day type (undetermined).** The checks are mixed. There is no read to act on, which is a normal result.

## Options

**0DTE.** An option that expires today. Its price reacts fast to both the index and the clock.

**At the money.** An option whose strike is at the current index price.

**Straddle.** A call plus a put at the same strike. Its price is the market's estimate of how far the index will move by the close, in either direction.

**Expected move.** That straddle price, read as a range around the current price. If the day's move is smaller, option buyers were overcharged; if it is bigger, they were undercharged.

**Implied volatility (IV).** How big a move option prices are assuming. Higher IV means more expensive options.

**IV crush.** Option prices are inflated at the open because overnight news has not been absorbed. Once the open is out of the way they deflate. The cards compare the straddle with its 09:35 ET price and treat a 20% drop as the crush being finished. Buying before that means paying for uncertainty that is about to disappear.

**VIX.** The market's 30-day volatility gauge, often called the fear gauge.

**VIX1D.** The same idea for the next one day. It is the best free read on whether today's options are cheap or expensive. The cards compare it with its last 20 days.

**Time value (extrinsic value).** The part of an option's price that is not already in the money. It is what melts away as the day goes on, slowly in the morning and fast in the last two hours.

**Theta.** The name for that melting. See the [theta table](premium.html#theta).

**Debit spread.** Buying one option and selling a further-out one against it. It costs less and loses less to deflating option prices, in exchange for a capped payoff. The cards suggest it when options are expensive and the day is trending.

**Premium cap.** The most you allow yourself to pay for an option in the late window. It is your number, set in `playbook.yaml`.

## Playbooks

**Early setup.** Your 10:00–13:00 ET playbook: a trade in the direction of the day, off the first 30 minutes' range, once option prices have deflated.

**Late setup.** Your 14:30–15:45 ET playbook: a trade on one objective trigger, with a cap on what you pay.

**Trigger.** The specific thing that has to happen before a setup counts. It tells you when, not why.

**Invalidation ("it is off on...").** What would show the idea is wrong.

**Time stop ("out by...").** A time after which the trade is closed whatever it is doing.

**Flat.** Holding no position.

## The calendar

**Options expiration.** The day an option stops existing. SPX has options expiring every trading day, so the question each day is whether anything bigger expires too.

**Weekly expiry.** The last trading day of the week, normally Friday. That week's options on stocks and ETFs expire at the close, on top of SPX's same-day options.

**Monthly options expiration ("opex").** The third Friday of the month, the biggest regular expiry. The standard monthly SPX options settle on that morning's opening prices, so the open can be jumpy.

**Quarterly expiration ("triple witching").** The monthly expiration in March, June, September and December, when index futures expire too. Volume is usually far above normal at the open and in the final minutes.

**Pinning.** Price hovering near a heavily traded strike, usually a round number, as expiry approaches. It is a tendency on big expiry days, not a rule, and the cards do not measure it.

**VIX settlement.** One Wednesday morning a month, VIX futures and options settle using SPX option prices at the open, which can make the first minutes noisier.

**Month-end and quarter-end.** The last trading day of the period. End-of-month SPX options expire and large funds rebalance their holdings, which can push price into the close for reasons unrelated to the day's news.

**Scheduled release.** Economic data or a Fed decision published at a known time (jobs report, CPI, the Fed statement). Price and option prices can jump within seconds of it, so a read made before it can stop being true when it lands.
