# Journal

`trades.csv` is filled in by hand, one row per trade. Nothing in this repo writes to it or reads a brokerage account.

| column | meaning |
|---|---|
| `date` | session date, YYYY-MM-DD |
| `playbook` | `early` or `late` |
| `regime` | the digest's label at entry (`trend_up`, `trend_down`, `balance`, `gap_and_go`, `gap_and_fill`, `undetermined`) |
| `entry_time`, `exit_time` | HH:MM ET |
| `strike` | option strike |
| `premium_paid` | per contract, in option points |
| `contracts` | number of contracts |
| `straddle_0935` | ATM straddle at 09:35 ET |
| `straddle_at_entry` | ATM straddle at entry |
| `extrinsic_entry`, `extrinsic_exit` | extrinsic value of the option at entry and exit |
| `trigger` | the trigger that qualified the entry |
| `spread_pct` | bid/ask spread as % of mid at entry |
| `exit_reason` | target, stop, time stop, invalidation, flat-by, other |
| `pnl_usd` | profit or loss in dollars |
| `pnl_r` | profit or loss in R (multiples of the amount put at stake) |
| `post_exit_note` | what price did after the exit |

`python -m digest journal` prints expectancy by playbook and by entry window once a playbook has at least 30 rows; before that it prints the row counts.
