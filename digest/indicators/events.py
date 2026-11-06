"""Calendar of catalysts for a session: FOMC, econ releases, auctions, Fed speakers, earnings, headlines."""
from __future__ import annotations

import re
from datetime import date, datetime

from digest import config

FED_CHAIR_PAT = re.compile(r"(Chair(man)?\b(?! for)|Vice Chair\b(?! for))", re.I)


def relevance_for(category: str, rules: dict) -> str:
    pr = rules.get("premium_relevance", {})
    if category in pr.get("high", []):
        return "high"
    if category in pr.get("medium", []):
        return "medium"
    return "low"


# Canonical schedule page per event category (shown as the event's source link).
BLS_URL = "https://www.bls.gov/schedule/news_release/"
BEA_URL = "https://www.bea.gov/news/schedule"
FED_URL = "https://www.federalreserve.gov/newsevents/calendar.htm"
EARNINGS_URL = "https://finance.yahoo.com/calendar/earnings"
CATEGORY_URL = {
    "CPI": BLS_URL, "PPI": BLS_URL, "NFP": BLS_URL, "GDP": BEA_URL, "PCE": BEA_URL,
    "RETAIL_SALES": "https://www.census.gov/economic-indicators/calendar-listview.html",
    "FOMC_DECISION": FED_URL, "FOMC_PRESS_CONFERENCE": FED_URL, "FOMC_MEETING_DAY1": FED_URL, "FOMC_MINUTES": FED_URL,
    "FED_SPEAKER": FED_URL, "FED_TESTIMONY": FED_URL,
    "MEGACAP_EARNINGS": EARNINGS_URL, "LARGECAP_EARNINGS": EARNINGS_URL,
    "AUCTION_10Y_20Y_30Y": "https://www.treasurydirect.gov/auctions/upcoming/", "AUCTION_OTHER": "https://www.treasurydirect.gov/auctions/upcoming/",
    "FF_HIGH": "https://www.forexfactory.com/calendar", "FF_MEDIUM": "https://www.forexfactory.com/calendar",
}

# ForexFactory rows that duplicate an event already in the official calendars are dropped.
FF_DUPLICATE_KEYS = {
    "CPI": ["cpi"], "NFP": ["non-farm", "nonfarm", "unemployment rate", "average hourly"], "PPI": ["ppi"],
    "RETAIL_SALES": ["retail sales"], "GDP": ["gdp"], "PCE": ["pce"],
    "FOMC_DECISION": ["federal funds rate", "fomc statement"], "FOMC_PRESS_CONFERENCE": ["fomc press"],
    "FOMC_MINUTES": ["fomc meeting minutes"], "FED_SPEAKER": ["speaks"], "FED_TESTIMONY": ["testifies"],
}


def _ev(d: str, time_et: str | None, name: str, category: str, rules: dict) -> dict:
    return {"date": d, "time_et": time_et, "name": name, "category": category,
            "premium_relevance": relevance_for(category, rules), "url": CATEGORY_URL.get(category)}


def ff_events(ff: list[dict] | None, d: date, existing: list[dict], rules: dict) -> list[dict]:
    if not ff:
        return []
    ds = d.isoformat()
    have = {e["category"] for e in existing}
    skip = [k for cat, keys in FF_DUPLICATE_KEYS.items() if cat in have for k in keys]
    out = []
    for r in ff:
        title = r.get("title", "")
        if r.get("date") != ds or any(k in title.lower() for k in skip):
            continue
        out.append(_ev(ds, r.get("time_et"), title, "FF_HIGH" if r.get("impact") == "High" else "FF_MEDIUM", rules))
    return out


def fomc_events(meetings: list[dict], d: date, rules: dict) -> list[dict]:
    out = []
    ds = d.isoformat()
    for m in meetings:
        if m.get("decision_date") == ds:
            sep = " (with SEP)" if m.get("sep") else ""
            out.append(_ev(ds, m.get("statement_time_et", "14:00"), f"FOMC statement{sep}", "FOMC_DECISION", rules))
            out.append(_ev(ds, m.get("press_conference_time_et", "14:30"), "FOMC press conference", "FOMC_PRESS_CONFERENCE", rules))
        elif m.get("start_date") == ds:
            out.append(_ev(ds, None, "FOMC meeting day 1 (no statement)", "FOMC_MEETING_DAY1", rules))
        if m.get("minutes_release_date") == ds:
            out.append(_ev(ds, "14:00", f"FOMC minutes (meeting ending {m['decision_date']})", "FOMC_MINUTES", rules))
    return out


def econ_events(econ: list[dict], d: date, rules: dict) -> list[dict]:
    ds = d.isoformat()
    return [_ev(ds, e.get("time_et"), e.get("title") or e["event"], e["event"], rules) for e in econ if e.get("date") == ds]


def auction_events(auctions: list[dict], d: date, rules: dict) -> list[dict]:
    ds = d.isoformat()
    out = []
    for a in auctions:
        if a.get("date") != ds:
            continue
        term = (a.get("security_term") or "").split("-")[0]
        cat = "AUCTION_10Y_20Y_30Y" if term in ("10", "20", "30") and a.get("security_type") in ("Note", "Bond") else "AUCTION_OTHER"
        out.append(_ev(ds, a.get("time_et"), a.get("event") or f"{a.get('security_term')} auction", cat, rules))
    return out


def _fed_time(t: str | None) -> str | None:
    if not t:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", t.strip(), re.I)
    if not m:
        return None
    h, mi = int(m.group(1)) % 12, int(m.group(2))
    if m.group(3).lower() == "p":
        h += 12
    return f"{h:02d}:{mi:02d}"


def fed_speaker_events(fed_cal: list[dict] | None, d: date, rules: dict) -> list[dict]:
    if not fed_cal:
        return []
    ds = d.isoformat()
    out = []
    for e in fed_cal:
        if e.get("type") not in ("Speeches", "Testimony"):
            continue
        if not e.get("month") or not e.get("days"):
            continue
        try:
            ed = f"{e['month']}-{int(str(e['days']).split(',')[0]):02d}"
        except ValueError:
            continue
        if ed != ds:
            continue
        cat = "FED_TESTIMONY" if e["type"] == "Testimony" else "FED_SPEAKER"
        out.append(_ev(ds, _fed_time(e.get("time")), (e.get("title") or "").strip(), cat, rules))
    return out


def earnings_events(earnings: dict | None, d: date, megacaps: list[str], rules: dict) -> list[dict]:
    if not earnings:
        return []
    ds = d.isoformat()
    out = []
    for item in earnings.get("items", []):
        if any(str(x)[:10] == ds for x in item.get("earnings_dates", [])):
            sym = item["symbol"]
            cat = "MEGACAP_EARNINGS" if sym in megacaps else "LARGECAP_EARNINGS"
            # yfinance gives the date only; before/after-the-bell timing is not available.
            out.append(_ev(ds, None, f"{sym} earnings (timing not in source)", cat, rules))
    return out


def events_for(d: date, sources: dict, rules: dict) -> list[dict]:
    ev = []
    ev += fomc_events(sources.get("fomc", []), d, rules)
    ev += econ_events(sources.get("econ", []), d, rules)
    ev += auction_events(sources.get("auctions", []), d, rules)
    ev += fed_speaker_events(sources.get("fed_calendar"), d, rules)
    ev += earnings_events(sources.get("earnings"), d, config.MEGACAPS, rules)
    ev += ff_events(sources.get("ff_calendar"), d, ev, rules)
    # De-duplicate (live auctions + static calendar overlap).
    seen, out = set(), []
    for e in sorted(ev, key=lambda e: (e["time_et"] or "99:99", e["name"])):
        k = (e["date"], e["time_et"], e["name"])
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def next_fomc(meetings: list[dict], d: date):
    upcoming = sorted(m["decision_date"] for m in meetings if m.get("decision_date") and m["decision_date"] >= d.isoformat())
    if not upcoming:
        return None, None
    nd = date.fromisoformat(upcoming[0])
    return upcoming[0], (nd - d).days


def high_event_later(events: list[dict], as_of: datetime, close_et: datetime | None):
    """Earliest high-relevance event with a time later than as_of and before the close."""
    now = as_of.astimezone(config.ET).strftime("%H:%M")
    close = close_et.strftime("%H:%M") if close_et else "16:00"
    later = [e for e in events if e["premium_relevance"] == "high" and e["time_et"] and now < e["time_et"] <= close]
    return (True, later[0]["time_et"]) if later else (False, None)
