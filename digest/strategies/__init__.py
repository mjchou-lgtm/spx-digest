"""Strategy *context* seam (no signals, no orders).

A Strategy reads a Brief and reports whether its preconditions hold and what
to watch. It never produces entries/exits and has no execution path — this
package intentionally has no broker client and nothing to send orders with.
"""
from digest.strategies.base import Strategy, StrategyRead
from digest.strategies.opening_range import OpeningRangeContext

REGISTRY: list[Strategy] = [OpeningRangeContext()]

__all__ = ["Strategy", "StrategyRead", "OpeningRangeContext", "REGISTRY"]
