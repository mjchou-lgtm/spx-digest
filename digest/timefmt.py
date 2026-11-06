"""Times are shown in both ET and PT everywhere."""
from __future__ import annotations


def pt_of(hhmm_et: str) -> str:
    h, m = map(int, hhmm_et.split(":"))
    return f"{(h - 3) % 24:02d}:{m:02d}"


def both(hhmm_et: str | None) -> str:
    """'10:30' -> '10:30 ET / 07:30 PT'."""
    if not hhmm_et:
        return "time n/a"
    return f"{hhmm_et} ET / {pt_of(hhmm_et)} PT"


import re

_ET = re.compile(r"\b(\d{2}:\d{2})(?:–(\d{2}:\d{2}))? ET\b(?! /)")


def with_pt(text: str) -> str:
    """Add the PT equivalent after every 'HH:MM ET' (or 'HH:MM–HH:MM ET') in a string."""
    def f(m):
        a, b = m.group(1), m.group(2)
        return f"{a}–{b} ET / {pt_of(a)}–{pt_of(b)} PT" if b else f"{a} ET / {pt_of(a)} PT"
    return _ET.sub(f, text)


def num(x) -> str:
    """Brief numbers as written in posts: up to 2 decimals, no trailing zeros, no thousands separator."""
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    return f"{x:.2f}".rstrip("0").rstrip(".")


_TRAILING_ZERO = re.compile(r"(?<=\d)\.0(?!\d)")


def tidy(x):
    """'7713.0' -> '7713' inside generated sentences (strings, or lists of strings)."""
    if isinstance(x, list):
        return [tidy(v) for v in x]
    return _TRAILING_ZERO.sub("", x) if isinstance(x, str) else x
