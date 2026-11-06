"""Plain-English wording for the cards. The reader is a retail trader who is still learning:
every term of art is either replaced or explained in a few words where it appears."""
from __future__ import annotations

REGIME_PLAIN = {
    "trend_up": "Uptrend day",
    "trend_down": "Downtrend day",
    "balance": "Range-bound day",
    "gap_and_go": "Gap-and-go day",
    "gap_and_fill": "Gap-and-fill day",
    "undetermined": "No clear day type",
}

REGIME_MEANS = {
    "trend_up": "buyers are in control and price keeps holding above its average for the day, so dips tend to be shallow.",
    "trend_down": "sellers are in control and price keeps holding below its average for the day, so bounces tend to be shallow.",
    "balance": "buyers and sellers roughly agree on price, so it rotates inside a range and moves toward the edges tend to fade.",
    "gap_and_go": "the market opened with a jump and kept going in that direction, so the jump is being accepted.",
    "gap_and_fill": "the market opened with a jump and then gave it back, returning to yesterday's prices.",
    "undetermined": "the evidence is mixed, so there is no read on the day to act on.",
}

LEAN_PLAIN = {
    "gap_up": "a gap up. Whether it keeps going or fills is decided then",
    "gap_down": "a gap down. Whether it keeps going or fills is decided then",
    "open_above_value": "an uptrend day, if the market holds above yesterday's value area",
    "open_below_value": "a downtrend day, if the market holds below yesterday's value area",
    "open_inside_value": "a range-bound day, because the market is set to open inside yesterday's value area",
}

LEVEL_PLAIN = {
    "prior high": "yesterday's high", "prior low": "yesterday's low", "prior close": "yesterday's close",
    "prior VAH": "top of yesterday's value area", "prior POC": "yesterday's most-traded price", "prior VAL": "bottom of yesterday's value area",
    "O/N high": "overnight high", "O/N low": "overnight low",
    "OR high": "top of the first 30 minutes", "OR low": "bottom of the first 30 minutes",
    "VWAP": "today's average price (VWAP)",
    "session high": "today's high", "session low": "today's low",
    "dev VAH": "top of today's value area", "dev POC": "today's most-traded price", "dev VAL": "bottom of today's value area",
}

EVENT_PLAIN = {
    "NFP": "Monthly jobs report (Employment Situation)",
    "CPI": "Consumer inflation (CPI)",
    "PPI": "Producer inflation (PPI)",
    "PCE": "PCE inflation, the Fed's preferred gauge",
    "GDP": "GDP (economic growth)",
    "RETAIL_SALES": "Retail sales",
    "FOMC_DECISION": "Fed interest-rate decision",
    "FOMC_PRESS_CONFERENCE": "Fed chair press conference",
    "FOMC_MINUTES": "Fed meeting minutes",
}

OR = "the first 30 minutes' range"
VWAP = "today's average price (VWAP)"
PRIOR_VA = "yesterday's value area"
DEV_VA = "today's value area"


def level_name(name: str) -> str:
    return "round number" if name.startswith("round ") else LEVEL_PLAIN.get(name, name)


def count(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four"}.get(int(n), str(n))


def closes(n: int) -> str:
    """'two 5-minute closes in a row' (a close is where a 5-minute bar finishes)."""
    return "a 5-minute close" if int(n) == 1 else f"{count(n)} 5-minute closes in a row"
