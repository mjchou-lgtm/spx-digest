"""Claude-written narrative from the structured brief. One API call per post.

The model only writes prose. Every number and the regime label come from
brief.json; the response is validated (template, regime header, forbidden
phrases) and any failure falls back to the brief rendered as a table.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from digest import config
from digest.brief import Brief

SECTIONS_BASE = ["## Regime:", "## What matters today", "## Levels to watch", "## What would change the read"]


def template_for(post_type: str) -> str:
    parts = []
    if post_type in ("midsession", "afternoon"):
        parts.append("## Since the last post\n2–4 bullets: what resolved versus the prior post's read.")
    parts.append("## Regime: <LABEL> (<confidence>)\nOne paragraph: what kind of day this looks like and why.")
    parts.append("## What matters today\n3–6 bullets: catalysts with times, vol structure, positioning context.")
    parts.append("## Levels to watch\nBullets: key levels from the brief with the reason each matters.")
    parts.append("## What would change the read\n2–3 bullets: what would flip the regime label.")
    if post_type == "afternoon":
        parts.append("## Into the close\n2–4 bullets: pin vs expansion, charm/gamma considerations into the close, what to carry into tomorrow's premarket.")
    return "\n\n".join(parts)


def required_headers(post_type: str) -> list[str]:
    h = list(SECTIONS_BASE)
    if post_type in ("midsession", "afternoon"):
        h.insert(0, "## Since the last post")
    if post_type == "afternoon":
        h.append("## Into the close")
    return h


POST_PURPOSE = {
    "premarket": "pre-market primer (05:45 PT): overnight action, today's calendar, and the regime going into the open",
    "midsession": "mid-session update (09:30 PT): how the open resolved and whether the regime is confirmed or changing",
    "afternoon": "afternoon update (last ~75 minutes of the session): pin vs expansion behaviour, charm/gamma into the close, what carried",
}


def system_prompt(post_type: str) -> str:
    return f"""You write one section of a daily SPX market digest: the {POST_PURPOSE[post_type]}.

Reader: an experienced SPX 0DTE options trader who reads this on a phone before and during the session. They want a macro read on the session — regime, catalysts that could move premiums, whether the day looks trending, choppy, or not worth engaging — not a signal service. Entries, exits, risk and sizing are entirely their call.

Content rules:
- Do not comment on risk, risk management, position sizing, or how risky 0DTE or single-leg options are. Add no disclaimers and no "not financial advice" language. The reader knows.
- Do not make trade calls: no specific entries, exits, strikes to buy or sell, stops or targets. Describe regime, levels, catalysts, and what to watch for.
- Use only numbers that appear in the brief, written exactly as given (same digits, no rounding, no new arithmetic such as differences or percentages you computed). If a value is null, say it is unavailable or leave it out; never estimate it.
- State the regime label and confidence exactly as given in brief.regime (for example "## Regime: RANGE (medium)"). You may explain it using brief.regime.rules_fired; do not substitute your own label.
- The gamma figures are an approximate, OI-based estimate, not dealer positioning; if you mention them, call them approximate.
- Times: catalyst times in the brief are ET; the reader is in Pacific time. Give both when you mention a time.
- Style: plain, direct prose. No hype, no exclamation marks, no emoji. No headers other than the template's. Bullets are short.
- Length: at most about 450 words in total.

Output exactly this Markdown template, filling in each section, and nothing before or after it:

{template_for(post_type)}"""


def user_message(brief: Brief, prior_post: str | None, prior_label: str | None) -> str:
    parts = ["<brief>", brief.model_dump_json(indent=1, exclude={"data_quality": {"null_fields"}}), "</brief>"]
    if brief.data_quality.null_fields or brief.data_quality.fallbacks:
        parts += ["<data_gaps>", json.dumps({"null_fields": brief.data_quality.null_fields, "fallbacks": brief.data_quality.fallbacks}), "</data_gaps>"]
    if prior_post:
        parts += [f"<previous_post label=\"{prior_label}\">", prior_post.strip(), "</previous_post>"]
    parts.append("Write the post now, following the template.")
    return "\n".join(parts)


@dataclass
class NarrativeResult:
    ok: bool
    text: str | None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    request: dict | None = None
    response: dict | None = None


def load_forbidden(path=config.FORBIDDEN_PHRASES_PATH) -> list[str]:
    return [ln.strip().lower() for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]


def find_forbidden(text: str, phrases: list[str] | None = None) -> list[str]:
    low = text.lower()
    return [p for p in (phrases or load_forbidden()) if re.search(rf"\b{re.escape(p)}\b", low)]


NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def brief_numbers(brief: Brief) -> set[str]:
    nums: set[str] = set()

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            nums.add(_norm(str(x)))
        elif isinstance(x, str):
            for m in NUM_RE.findall(x):
                nums.add(_norm(m))
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(brief.model_dump())
    return nums


def _norm(s: str) -> str:
    s = s.replace(",", "").lstrip("+")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.lstrip("-") or "0"


def _pt_times(brief: Brief) -> set[str]:
    """ET times in the brief converted to PT (the prompt asks for both)."""
    out = set()
    times = [e.time_et for e in brief.calendar.events_today + brief.calendar.events_next_session if e.time_et]
    if brief.calendar.next_high_event_time_et:
        times.append(brief.calendar.next_high_event_time_et)
    for t in times:
        h, m = t.split(":")
        h_pt = (int(h) - 3) % 24
        out |= {f"{h_pt}", f"{h_pt:02d}", m, f"{h_pt % 12 or 12}"}
    return out


def unverified_numbers(text: str, brief: Brief) -> list[str]:
    """Numbers in the prose that do not appear in the brief (warnings, recorded in llm.json).

    Small integers (counts like "3 bullets", "9 of 11"), PT conversions of ET
    times, and dates are tolerated.
    """
    known = brief_numbers(brief) | _pt_times(brief)
    bad = []
    for m in NUM_RE.findall(text):
        n = _norm(m)
        if n in known:
            continue
        try:
            if float(n) <= 12 and "." not in n:
                continue
        except ValueError:
            pass
        bad.append(m)
    return sorted(set(bad))


def validate(text: str, brief: Brief) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors force the fallback rendering."""
    errors, warnings = [], []
    for h in required_headers(brief.meta.post_type):
        if h not in text:
            errors.append(f"missing section '{h}'")
    want = f"## Regime: {brief.regime.label} ({brief.regime.confidence})"
    if want not in text:
        errors.append(f"regime header must be '{want}'")
    hits = find_forbidden(text)
    if hits:
        errors.append(f"forbidden phrases: {hits}")
    un = unverified_numbers(text, brief)
    if un:
        warnings.append(f"numbers not found in brief: {un}")
    return errors, warnings


def generate(brief: Brief, prior_post: str | None, prior_label: str | None) -> NarrativeResult:
    import anthropic

    key = config.anthropic_key()
    sys_p = system_prompt(brief.meta.post_type)
    usr = user_message(brief, prior_post, prior_label)
    request = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": config.CLAUDE_MAX_TOKENS,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": config.CLAUDE_EFFORT},
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
        "system": sys_p,
        "messages": [{"role": "user", "content": usr}],
    }
    if not key:
        return NarrativeResult(ok=False, text=None, error="ANTHROPIC_API_KEY not set", request=request)
    client = anthropic.Anthropic(api_key=key, timeout=120, max_retries=2)
    try:
        resp = client.beta.messages.create(**request)
    except anthropic.APIStatusError as e:
        return NarrativeResult(ok=False, text=None, error=f"API {e.status_code}: {e.message}", request=request)
    except anthropic.APIConnectionError as e:
        return NarrativeResult(ok=False, text=None, error=f"connection error: {e}", request=request)
    resp_d = resp.model_dump(mode="json")
    if resp.stop_reason == "refusal":
        return NarrativeResult(ok=False, text=None, error=f"refusal: {resp_d.get('stop_details')}", request=request, response=resp_d)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if resp.stop_reason == "max_tokens":
        return NarrativeResult(ok=False, text=text, error="hit max_tokens (truncated)", request=request, response=resp_d)
    errors, warnings = validate(text, brief)
    if errors:
        return NarrativeResult(ok=False, text=text, error="; ".join(errors), warnings=warnings, request=request, response=resp_d)
    return NarrativeResult(ok=True, text=text, warnings=warnings, request=request, response=resp_d)
