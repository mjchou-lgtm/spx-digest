from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from digest.brief import Brief


@dataclass
class StrategyRead:
    name: str
    applicability: Literal["applicable", "not_applicable", "unknown"]
    conditions_met: list[str] = field(default_factory=list)
    conditions_unmet: list[str] = field(default_factory=list)
    what_to_watch: list[str] = field(default_factory=list)


@runtime_checkable
class Strategy(Protocol):
    name: str

    def describe(self) -> str: ...

    def evaluate(self, brief: Brief) -> StrategyRead: ...
