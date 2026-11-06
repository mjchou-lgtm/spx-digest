# Rules: the two playbooks

This table is rendered from `playbook.yaml`. A cell that says "not set" is a rule that has not been written into that file yet; the digest never fills one in.

{{rules_table}}

## Shared rules

- Trade the regime, not a view. Direction comes from the day type.
- Flat by the time shown above, before the closing-imbalance flow.
- High IV on a balance day: sit out.
- Gap-and-go is with-trend only.
- A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.

## How the cards use them

- The **mid-session card** says whether the early playbook is live, with its trigger, invalidation and time stop.
- The **afternoon card** names the one late trigger that qualifies and repeats the premium cap and the flat-by time.
- The digest reports whether the conditions are met. It does not place, size or manage a position.
