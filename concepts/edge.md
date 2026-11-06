# Edge: where it comes from

Three sources, strongest first.

## 1. Structural flows

Some participants must trade at known times: opening orders, hedges that change with the index, funds that trade at the close. These flows repeat because they come from mandates and mechanics, not opinions. See [daily structure](daily-structure.html).

## 2. Behavioural traps

Other participants trade badly at predictable moments: buying premium before the IV crush, chasing a breakout that closes back inside the range, fading a gap-and-go, adding to a losing position late in the day when gamma is highest. Each of these transfers money to whoever is on the other side.

## 3. Regime identification

The same setup works on one kind of day and fails on another. A break of the opening range means something on a trend day and little on a balance day. Knowing the day type decides which playbook applies and which does not. This is what the digest's classifier is for, and why "undetermined" is a valid answer.

## Triggers are timing, not thesis

An entry trigger (acceptance beyond the opening range, a break of a confluence level with volume returning) says *when*. It does not say *why*. The reason for a trade is the regime and the flow behind it; the trigger only times the entry once that reason is already in place. A trigger without a regime behind it is a pattern with no cause.

## What follows

- A day with no clear regime has no trade. That is an outcome, not a miss.
- The two playbooks stay separate. The early one is a conviction trade on the day type; the late one is an execution trade on an objective trigger. Mixing them takes the worst of both.
- The journal measures expectancy by playbook and by entry window, because edge that cannot be measured cannot be told apart from luck.
