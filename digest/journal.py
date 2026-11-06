"""Journal summary: expectancy by playbook and by entry window. Reads journal/trades.csv only."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

FIELDS = ["date", "playbook", "regime", "entry_time", "exit_time", "strike", "premium_paid", "contracts", "straddle_0935",
          "straddle_at_entry", "extrinsic_entry", "extrinsic_exit", "trigger", "spread_pct", "exit_reason", "pnl_usd", "pnl_r",
          "post_exit_note"]
MIN_ROWS = 30
# Entry windows (ET), [start, end).
WINDOWS = [("10:00", "11:00"), ("11:00", "12:00"), ("12:00", "13:00"), ("13:00", "14:30"), ("14:30", "15:00"), ("15:00", "15:45")]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (r.get("date") or "").strip()]


def window_of(entry_time: str) -> str:
    t = (entry_time or "").strip()[:5]
    for a, b in WINDOWS:
        if a <= t < b:
            return f"{a}–{b} ET"
    return "other"


def expectancy(rows: list[dict]) -> dict:
    r = [x for x in (_f(row.get("pnl_r")) for row in rows) if x is not None]
    usd = [x for x in (_f(row.get("pnl_usd")) for row in rows) if x is not None]
    wins, losses = [x for x in r if x > 0], [x for x in r if x <= 0]
    return {
        "n": len(rows), "n_r": len(r),
        "win_rate_pct": 100 * len(wins) / len(r) if r else None,
        "avg_win_r": sum(wins) / len(wins) if wins else None,
        "avg_loss_r": sum(losses) / len(losses) if losses else None,
        "expectancy_r": sum(r) / len(r) if r else None,
        "expectancy_usd": sum(usd) / len(usd) if usd else None,
    }


def _line(name: str, e: dict) -> str:
    def s(v, unit=""):
        return "n/a" if v is None else f"{v:+.2f}{unit}"
    wr = "n/a" if e["win_rate_pct"] is None else f"{e['win_rate_pct']:.0f}%"
    return (f"  {name:<18} n={e['n']:<4} win rate {wr:<5} avg win {s(e['avg_win_r'], 'R'):<8} avg loss {s(e['avg_loss_r'], 'R'):<8} "
            f"expectancy {s(e['expectancy_r'], 'R')} / ${s(e['expectancy_usd'])}")


def summary_text(path: Path) -> str:
    rows = load(path)
    by_pb: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_pb[(r.get("playbook") or "unlabelled").strip().lower()].append(r)
    out = [f"{len(rows)} journal rows in {path}"]
    for pb in sorted(set(by_pb) | {"early", "late"}):
        rs = by_pb.get(pb, [])
        if len(rs) < MIN_ROWS:
            out.append(f"{pb}: {len(rs)} rows; expectancy is reported from {MIN_ROWS} rows ({MIN_ROWS - len(rs)} to go)")
            continue
        out.append(f"{pb}:")
        out.append(_line("all", expectancy(rs)))
        by_w: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            by_w[window_of(r.get("entry_time", ""))].append(r)
        for w in sorted(by_w):
            out.append(_line(w, expectancy(by_w[w])))
    return "\n".join(out)
