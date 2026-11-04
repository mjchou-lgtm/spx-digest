"""Example strategy context: has the opening range formed, and where is spot relative to it?"""
from __future__ import annotations

from digest.brief import Brief
from digest.strategies.base import StrategyRead


class OpeningRangeContext:
    name = "opening_range_context"

    def describe(self) -> str:
        return "Reports whether the first-30-minute opening range has formed and where spot sits relative to it. No signals."

    def evaluate(self, brief: Brief) -> StrategyRead:
        i = brief.intraday
        if brief.meta.post_type == "premarket" or i.or_high is None:
            return StrategyRead(self.name, "unknown", conditions_unmet=["opening range not formed (before or at the open)"],
                                what_to_watch=["first 30 minutes of the session"])
        if not i.or_complete:
            return StrategyRead(self.name, "unknown", conditions_unmet=["opening range still forming"],
                                what_to_watch=[f"range so far {i.or_low}–{i.or_high}"])
        met = [f"opening range formed: {i.or_low}–{i.or_high}", f"spot is {i.spot_vs_or} the opening range"]
        return StrategyRead(self.name, "applicable", conditions_met=met,
                            what_to_watch=[f"OR high {i.or_high}", f"OR low {i.or_low}"])
