# Premium: IV crush, theta and breakeven

A 0DTE option's price is intrinsic value plus extrinsic value. Extrinsic value is what decays, and two different things take it away.

## IV crush versus theta

- **IV crush** is a repricing. The open carries overnight uncertainty; once it clears, implied vol falls and the ATM straddle drops faster than the clock alone explains. The digest compares the straddle with its 09:35 ET / 06:35 PT print and calls the crush done at −20% or lower.
- **Theta** is the clock. With vol unchanged, ATM extrinsic value shrinks roughly with the square root of the time left.

An option bought before the crush pays for vol that is about to leave. An option bought after it pays mostly for time.

## Theta reference {: #theta }

ATM extrinsic value remaining, square-root-of-time model, normal 09:30–16:00 ET session:

{{theta_table}}

The model assumes implied vol stays put. A vol spike adds extrinsic value back; a crush removes more than the table shows.

## Breakeven move

For a single long option held over a short window:

**breakeven move ≈ extrinsic value lost over the hold ÷ delta**

An ATM option with a delta near 0.5 that loses 2 points of extrinsic value needs about a 4-point move in its favour to break even. Later in the day the same hold loses more extrinsic value per minute, so the move has to come sooner.

## Variance per contract, early versus late

- **Early**: more extrinsic value, lower gamma. The option's price moves less per index point, and time decay is slow. Outcomes per contract are spread less widely.
- **Late**: little extrinsic value, high gamma. A few index points move the price by a large fraction of the premium, in either direction. Outcomes per contract are spread widely, which is why the late playbook is capped by premium.

## When a debit spread helps

A debit spread sells a further-out option against the one bought. The short leg gives back part of the extrinsic value and part of the vega, so the position loses less to a fall in implied vol and to decay. The cost is a capped payoff. It helps most when implied vol is high (VIX1D high or extreme against its last 20 closes) and the regime is a trend; that is the case the digest flags.

## The expected move

The ATM straddle price is the market's implied move for the rest of the session: straddle ÷ spot. On a high-IV day the useful question is whether the regime is likely to exceed that move, not whether the premium looks expensive.
