"""Claude writes the VERDICT line and a short narrative from the structured fields. One API call per post.

Every number, the regime label and the playbook status come from brief.json. The response
is validated (verdict phrases, length, forbidden phrases, numbers); on any failure the card
is published with the computed verdict and no narrative.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from digest import config
from digest.brief import Brief

MAX_WORDS = 80
HARD_MAX_WORDS = 110  # over MAX_WORDS is a warning; over this the card is published without the narrative

POST_PURPOSE = {
    "premarket": "pre-market card (09:15 ET / 06:15 PT): likely day type and which playbook could go live",
    "midsession": "mid-session card (10:45 ET / 07:45 PT): the classified regime and whether the early playbook is live",
    "afternoon": "afternoon card (14:15 ET / 11:15 PT): whether the regime held and whether the late playbook is live",
}


def system_prompt(post_type: str) -> str:
    return f"""You write two things for one card of a daily SPX 0DTE digest, the {POST_PURPOSE[post_type]}: a VERDICT line and a very short narrative. Code renders every other part of the card from the same JSON you are given: a "what to watch" list under your verdict, then Technical and News / macro sections.

Reader: a retail trader who uses this card as a learning tool. They are not deep into technical analysis, so do not assume they know the jargon. Write in plain English, the way you would explain the day to a smart friend. If you need a term of art (VWAP, value area, IV crush, straddle, debit spread), say what it means in a few words the first time, or use the plain version instead ("today's average price", "the zone where most of yesterday's trading happened", "option prices deflating after the open"). Say why a thing matters, not only what it is.

About the reader's approach, so you can interpret the fields: single-leg, defined-risk SPX 0DTE trades, flat by 15:45 ET, trading the kind of day it is and not a directional view. Two playbooks, kept separate: early (10:00–13:00 ET, off the first 30 minutes' range once option prices have deflated after the open) and late (14:30–15:45 ET, on one objective trigger, with a cap on premium).

Rules:
- Reference only fields in the JSON. Use only numbers that appear in it, written exactly as given (same digits, no rounding, no new arithmetic). If a value is null, say it is unavailable or leave it out; never estimate it.
- The day type (regime.label), playbook status, triggers and invalidations are computed by code. State them as given. Do not substitute your own label, and do not invent triggers, strikes, entries, exits, sizes, stops or targets that are not in the JSON.
- On high-IV days (vol.iv_high true) do not say premium is expensive or to avoid it. Say whether the expected move the straddle implies looks likely to be exceeded given the regime, using the fields. High IV with a trend regime means the early playbook with a debit spread to consider; high IV with balance means sit out.
- A no-trade outcome is a valid verdict; state it plainly when the playbook is none or pending.
- Weigh the calendar when you read the evidence, and say so in one plain sentence when it changes the picture. The fields: calendar.weekday; calendar.expiry_kind ("weekly", "monthly" or "quarterly" means more options than usual expire today, which can hold price near heavily traded round-number strikes in the afternoon and speed up the last hour; on "monthly" and "quarterly" days the standard monthly SPX options settle on the opening prices, so the open can be jumpy); calendar.opex_week; calendar.month_end and calendar.quarter_end (fund rebalancing can push price into the close); calendar.vix_expiry_today (noisier open); meta.is_early_close; and the scheduled releases in calendar.events_today, especially a high-impact one still ahead (calendar.high_event_later_today, calendar.next_high_event_time_et), which can change the read the moment it lands. These are tendencies, not forecasts: say "can" or "often", never that it will happen. On an ordinary day with nothing of the kind, leave the calendar out.
- Add no disclaimers, no "not financial advice" language, and no commentary on how risky options are. The reader knows.
- Times: give every time in both zones, ET first, for example "10:30 ET / 07:30 PT".
- Style: short, plain sentences. No hype, no exclamation marks, no emoji, no headers, no links, no abbreviations the reader would have to look up.

Output exactly this, and nothing before or after it:

VERDICT: <one short line in plain English{_verdict_hint(post_type)}>

<narrative: at most {MAX_WORDS} words, two to four short plain sentences: what today's evidence adds up to, why it matters for someone trading options today, and the one thing to watch next. The card already lists the levels, option-price numbers and triggers right around your text, so do not recite them; use a number only when the point needs it.>"""


def _verdict_hint(post_type: str) -> str:
    return {
        "premarket": ': the likely kind of day from regime.lean, and that there is no trade until the day type is set at 10:30 ET / 07:30 PT',
        "midsession": ": the kind of day in plain words with the label in brackets, then the playbook status, for example \"Range-bound day (balance); playbook: none\"",
        "afternoon": ": whether this morning's read is confirmed or changed, in plain words with the label in brackets, then \"late playbook live\" or \"late playbook not live\"",
    }[post_type]


def user_message(brief: Brief, prior_verdict: str | None = None) -> str:
    from digest.render import verdict_requirements

    payload = brief.model_dump_json(indent=1, exclude={"data_quality": {"null_fields", "sources"}})
    parts = ["<fields>", payload, "</fields>"]
    if prior_verdict:
        parts += ["<previous_verdict>", prior_verdict.strip(), "</previous_verdict>"]
    req = ", ".join(f'"{r}"' for r in verdict_requirements(brief))
    parts.append(f"Write the VERDICT line and the narrative now. The VERDICT line must contain these exact phrases: {req}.")
    return "\n".join(parts)


@dataclass
class NarrativeResult:
    ok: bool
    text: str | None
    error: str | None = None
    verdict: str | None = None
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
    return out | {"00", "15", "30", "35", "45"}  # minutes of the fixed session times


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


def split_output(text: str) -> tuple[str | None, str]:
    """(verdict line without the label, narrative)."""
    lines = text.strip().splitlines()
    if not lines or not lines[0].upper().startswith("VERDICT:"):
        return None, text.strip()
    return lines[0].split(":", 1)[1].strip(), "\n".join(lines[1:]).strip()


def validate(text: str, brief: Brief) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors drop Claude's text; the card is published with the computed verdict."""
    from digest.render import verdict_requirements

    errors, warnings = [], []
    verdict, body = split_output(text)
    if verdict is None:
        errors.append("output must start with 'VERDICT:'")
    else:
        for req in verdict_requirements(brief):
            if req not in verdict:
                errors.append(f"verdict must contain '{req}'")
    if re.search(r"^#{1,6} ", body, re.M):
        errors.append("narrative must not contain headers")
    words = len(body.split())
    if words > HARD_MAX_WORDS:
        errors.append(f"narrative is {words} words (limit {MAX_WORDS})")
    elif words > MAX_WORDS:
        warnings.append(f"narrative is {words} words (limit {MAX_WORDS})")
    hits = find_forbidden(text)
    if hits:
        errors.append(f"forbidden phrases: {hits}")
    un = unverified_numbers(text, brief)
    if un:
        warnings.append(f"numbers not found in fields: {un}")
    return errors, warnings


def generate(brief: Brief, prior_verdict: str | None = None) -> NarrativeResult:
    import anthropic

    key = config.anthropic_key()
    sys_p = system_prompt(brief.meta.post_type)
    usr = user_message(brief, prior_verdict)
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
    verdict, body = split_output(text)
    return NarrativeResult(ok=True, text=body, verdict=verdict, warnings=warnings, request=request, response=resp_d)
