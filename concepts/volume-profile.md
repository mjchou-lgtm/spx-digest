# Volume profile: POC, value area and shapes

A volume profile counts how much traded at each price over a period, instead of when it traded.

## The terms

- **POC (point of control)**: the price with the most volume. The market's most-accepted price for the period.
- **Value area (VA)**: the band around the POC holding 70% of the volume. **VAH** and **VAL** are its high and low.
- **HVN / LVN**: high- and low-volume nodes. Price tends to slow and rotate at an HVN and to pass through an LVN quickly, because few participants transacted there.
- **Acceptance**: price trades and closes beyond a level and stays. The digest uses two consecutive 5-minute closes. A probe that closes back inside is a rejection.
- **Absorption**: heavy volume at a level without progress. Selling absorbed at a low, or buying absorbed at a high, shows resting orders taking the other side.

## Reading the open against prior value

- **Open inside the prior value area**: the market starts where it agreed yesterday. Rotation is the default, and VWAP is usually crossed both ways.
- **Open outside the prior value area**: yesterday's agreement is being rejected. Either price is accepted outside value (trend) or it returns to it (fill).

## Shapes

| Shape | Looks like | Reads as |
|---|---|---|
| D | POC mid-range, volume tapering both ways | Balance: two-sided trade |
| P | POC in the upper third, thin tail below | A rally that then held high: short covering or buying that stalled |
| b | POC in the lower third, thin tail above | A sell-off that then held low: long liquidation or selling that stalled |
| elongated | Volume spread thinly along the range, no dominant node | Trend: price kept moving and did not build value |

## Caveats

- **VPVR depends on the window.** A visible-range profile on a chart changes when the chart is scrolled or zoomed. A session profile is fixed to one session. The digest uses session profiles only.
- **The digest's profile is coarse.** It is built from 5-minute bars in 1-point bins, with each SPX bar's range weighted by SPY volume because the index has no volume. A tick-based futures profile will differ by a few points.
- The developing profile changes all day. Its POC and value area in the afternoon card are as of that card's timestamp.
