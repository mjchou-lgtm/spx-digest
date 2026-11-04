"""Post markdown: YAML frontmatter + body (Claude narrative, dry-run bullets, or fallback table)."""
from __future__ import annotations

import yaml

from digest.brief import Brief

LABEL_ICON = {
    "TREND_UP": "▲",
    "TREND_DOWN": "▼",
    "RANGE": "↔",
    "EVENT_WAIT": "⏸",
    "VOL_EXPANSION": "⚡",
    "NO_TRADE": "⛔",
}

SECTION_TITLES = {
    "levels": "Levels",
    "vol": "Volatility",
    "positioning": "Positioning (approximate, OI-based)",
    "cross_asset": "Cross-asset",
    "breadth": "Breadth / leadership",
    "intraday": "Intraday",
}


def frontmatter(brief: Brief, narrative: str, files: dict, model: str | None) -> dict:
    return {
        "date": brief.meta.date,
        "post_type": brief.meta.post_type,
        "version": brief.meta.version,
        "regime": brief.regime.label,
        "confidence": brief.regime.confidence,
        "generated_at": brief.meta.generated_at,
        "data_as_of": brief.meta.data_as_of,
        "schema_version": brief.meta.schema_version,
        "narrative": narrative,  # claude | unavailable | dry-run
        "model": model,
        "files": files,
    }


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v) if v else "—"
    if isinstance(v, dict):
        return ", ".join(f"{k} {fmt(x)}" for k, x in v.items()) if v else "—"
    return str(v)


def _events_md(events, empty: str) -> list[str]:
    if not events:
        return [f"- {empty}"]
    return [f"- {e.time_et or 'time n/a'} ET — {e.name} [{e.premium_relevance}]" for e in events]


def regime_header(brief: Brief) -> str:
    return f"## Regime: {brief.regime.label} ({brief.regime.confidence})"


def bullets_body(brief: Brief) -> str:
    """--dry-run body: the brief as bullet points (no Claude call)."""
    lines = [regime_header(brief), "", "Rules fired:", ""]
    lines += [f"- {r}" for r in brief.regime.rules_fired] or ["- none"]
    lines += ["", "## Calendar today"] + _events_md(brief.calendar.events_today, "no scheduled catalysts in calendars")
    lines += ["", f"## Next session ({brief.calendar.next_session_date})"] + _events_md(brief.calendar.events_next_session, "none listed")
    for sec, title in SECTION_TITLES.items():
        items = [(k, v) for k, v in getattr(brief, sec) if v not in (None, [], {}) and k not in ("gex_method",)]
        if not items:
            continue
        lines += ["", f"## {title}"] + [f"- {k}: {fmt(v)}" for k, v in items]
    if brief.calendar.headlines:
        lines += ["", "## Headlines"] + [f"- {h.title} ({h.source})" for h in brief.calendar.headlines]
    return "\n".join(lines) + "\n"


def table_body(brief: Brief, reason: str) -> str:
    """Fallback when the narrative call fails: banner + brief as a table."""
    lines = [
        '<div class="banner" role="status">⚠ Narrative unavailable — showing the computed brief.</div>',
        "",
        regime_header(brief),
        "",
        "| Rule fired |",
        "|---|",
    ]
    lines += [f"| {r} |" for r in brief.regime.rules_fired] or ["| none |"]
    lines += ["", "## Calendar today"] + _events_md(brief.calendar.events_today, "no scheduled catalysts in calendars")
    for sec, title in SECTION_TITLES.items():
        rows = [(k, v) for k, v in getattr(brief, sec) if v not in (None, [], {}) and k != "gex_method"]
        if not rows:
            continue
        lines += ["", f"## {title}", "", "| Field | Value |", "|---|---|"] + [f"| {k} | {fmt(v)} |" for k, v in rows]
    # The failure reason is recorded in <post>.llm.json, not in the post (it may quote forbidden text).
    return "\n".join(lines) + "\n"


def post_markdown(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def split_post(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")
