"""Static calendars in calendars/*.json and the scripts that refresh them.

Refresh: `python -m digest refresh-calendars [--year 2026]` (also run weekly by
.github/workflows/refresh-calendars.yml). Refreshes merge: existing entries
are kept, new ones are added, so a source outage never empties a calendar.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from digest import config
from digest.fetch.base import http_get
from digest.fetch.web import fetch_fed_calendar, fetch_fred_release_dates, fetch_treasury_upcoming

log = logging.getLogger("digest.calendars")

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# FRED release ids for BLS/Census releases (BLS blocks automated clients, so
# FRED's release calendar is the source). Each id is checked against the
# release name before use. Times are the agencies' standard release times (ET).
FRED_RELEASES = {
    "CPI": {"id": 10, "name_contains": "consumer price index", "time_et": "08:30", "agency": "BLS"},
    "PPI": {"id": 46, "name_contains": "producer price index", "time_et": "08:30", "agency": "BLS"},
    "NFP": {"id": 50, "name_contains": "employment situation", "time_et": "08:30", "agency": "BLS"},
    "RETAIL_SALES": {"id": 9, "name_contains": "retail", "time_et": "08:30", "agency": "Census"},
}
# BEA schedule rows we keep, matched on the release title.
BEA_PATTERNS = {
    "GDP": re.compile(r"^GDP \((advance|second|third)", re.I),
    "PCE": re.compile(r"^Personal Income and Outlays", re.I),
}


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")


def _merge_events(existing: list[dict], new: list[dict], key=("date", "event")) -> list[dict]:
    seen = {tuple(e.get(k) for k in key): e for e in existing}
    for e in new:
        seen[tuple(e.get(k) for k in key)] = {**seen.get(tuple(e.get(k) for k in key), {}), **e}
    return sorted(seen.values(), key=lambda e: (e.get("date") or "", e.get("time_et") or "", e.get("event") or ""))


def _fed_time_to_hhmm(t: str | None) -> str | None:
    if not t:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", t.strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


# --- FOMC -------------------------------------------------------------------------

def parse_fomc_page(html: str, year: int) -> list[dict]:
    """Meetings from federalreserve.gov/monetarypolicy/fomccalendars.htm."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for panel in soup.select("div.panel"):
        head = panel.select_one(".panel-heading")
        if not head or f"{year} FOMC Meetings" not in head.get_text(" ", strip=True):
            continue
        for row in panel.select(".fomc-meeting"):
            month_txt = row.select_one(".fomc-meeting__month").get_text(strip=True)
            date_txt = row.select_one(".fomc-meeting__date").get_text(strip=True)
            sep = "*" in date_txt
            days = re.findall(r"\d+", date_txt)
            months = [MONTHS[m.lower()] for m in re.split(r"[/-]", month_txt) if m.lower() in MONTHS]
            if not days or not months:
                continue
            end_month = months[-1]
            start_month = months[0]
            start = date(year, start_month, int(days[0]))
            end = date(year, end_month, int(days[-1]))
            minutes_el = row.select_one(".fomc-meeting__minutes")
            minutes_release = None
            if minutes_el:
                m = re.search(r"Released (\w+) (\d{1,2}), (\d{4})", minutes_el.get_text(" ", strip=True))
                if m and m.group(1).lower() in MONTHS:
                    minutes_release = date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
            out.append(
                {
                    "start_date": start.isoformat(),
                    "decision_date": end.isoformat(),
                    "statement_time_et": "14:00",
                    "press_conference_time_et": "14:30",
                    "sep": sep,
                    "minutes_release_date": minutes_release,
                }
            )
    return out


def refresh_fomc(year: int) -> Path:
    path = config.CALENDARS_DIR / f"fomc_{year}.json"
    cur = _load(path)
    meetings = parse_fomc_page(http_get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm").text, year)
    if not meetings:
        raise RuntimeError("FOMC page parsed to zero meetings — layout changed?")
    # Future minutes dates come from the Fed calendar JSON.
    cal = fetch_fed_calendar()
    if cal.ok:
        for e in cal.data:
            if e.get("type") == "FOMC" and (e.get("title") or "").strip() == "FOMC Minutes" and (e.get("month") or "").startswith(str(year)):
                d = f"{e['month']}-{int(e['days']):02d}"
                # Minutes are released three weeks after the meeting they cover.
                for mtg in meetings:
                    if mtg["minutes_release_date"] is None and 18 <= (date.fromisoformat(d) - date.fromisoformat(mtg["decision_date"])).days <= 25:
                        mtg["minutes_release_date"] = d
    _save(path, {
        "source": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "refreshed_at": datetime.now(config.UTC).isoformat(timespec="seconds"),
        "year": year,
        "meetings": meetings or cur.get("meetings", []),
    })
    return path


# --- Economic releases -------------------------------------------------------------

def parse_bea_schedule(html: str, year: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        m = re.match(r"(\w+) (\d{1,2})", cells[0])
        if not m or m.group(1).lower() not in MONTHS:
            continue
        title = cells[-1]
        for event, pat in BEA_PATTERNS.items():
            if pat.search(title):
                t = re.search(r"(\d{1,2}):(\d{2})\s*([AP])\.?M", cells[0], re.I)
                hh = None
                if t:
                    h = int(t.group(1)) % 12 + (12 if t.group(3).upper() == "P" else 0)
                    hh = f"{h:02d}:{t.group(2)}"
                out.append({
                    "date": date(year, MONTHS[m.group(1).lower()], int(m.group(2))).isoformat(),
                    "event": event,
                    "title": title,
                    "time_et": hh,
                    "agency": "BEA",
                })
    return out


def refresh_econ(year: int) -> tuple[Path, list[str]]:
    path = config.CALENDARS_DIR / f"econ_{year}.json"
    cur = _load(path)
    events = list(cur.get("events", []))
    problems = []
    try:
        events = _merge_events(events, parse_bea_schedule(http_get(config.BEA_SCHEDULE_URL).text, year))
    except Exception as e:  # noqa: BLE001
        problems.append(f"BEA schedule: {e}")
    for event, spec in FRED_RELEASES.items():
        if not config.fred_key():
            problems.append(f"{event}: FRED_API_KEY not set; BLS/Census dates not refreshed")
            continue
        try:
            rel = http_get(f"{config.FRED_BASE}/release", params={
                "release_id": spec["id"], "api_key": config.fred_key() or "", "file_type": "json"}).json()
            name = (rel.get("releases") or [{}])[0].get("name", "")
            if spec["name_contains"] not in name.lower():
                raise RuntimeError(f"FRED release {spec['id']} is '{name}', expected '{spec['name_contains']}'")
            new = [{"date": d, "event": event, "title": name, "time_et": spec["time_et"], "agency": spec["agency"]}
                   for d in fetch_fred_release_dates(spec["id"], year)]
            events = _merge_events(events, new)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{event} via FRED: {e}")
    _save(path, {
        "sources": {
            "BEA": config.BEA_SCHEDULE_URL,
            "BLS/Census (via FRED release calendar)": "https://fred.stlouisfed.org/releases/calendar",
        },
        "refreshed_at": datetime.now(config.UTC).isoformat(timespec="seconds"),
        "year": year,
        "events": events,
    })
    return path, problems


# --- Treasury auctions ---------------------------------------------------------------

def refresh_auctions() -> Path:
    path = config.CALENDARS_DIR / "auctions.json"
    cur = _load(path)
    res = fetch_treasury_upcoming()
    if not res.ok:
        raise RuntimeError(res.error)
    new = [
        {
            "date": r["auction_date"],
            "event": f"{r['security_term']} {r['security_type']} auction",
            "security_type": r["security_type"],
            "security_term": r["security_term"],
            "time_et": _fed_time_to_hhmm((r["close_time_et"] or "").replace("PM", "p.m.").replace("AM", "a.m.")),
            "offering_amount": r["offering_amount"],
        }
        for r in res.data
        if r["auction_date"] and r["security_type"] in ("Note", "Bond", "TIPS", "FRN")
    ]
    _save(path, {
        "source": config.TREASURY_UPCOMING_URL,
        "note": "Only announced auctions (about one week ahead). Refreshed weekly; also fetched live each run.",
        "refreshed_at": datetime.now(config.UTC).isoformat(timespec="seconds"),
        "events": _merge_events(cur.get("events", []), new),
    })
    return path


# --- Large-cap earnings watchlist ----------------------------------------------------

def refresh_large_caps(threshold_usd: float = 200e9) -> Path:
    """Re-rank the candidate list by market cap; keep names above the threshold.

    TODO: candidates are a hand-maintained superset; replace with the full
    S&P 500 constituent list if a stable free source is chosen.
    """
    import yfinance as yf

    path = config.CALENDARS_DIR / "large_caps.json"
    cur = _load(path)
    candidates = sorted(set(cur.get("candidates", [])) | set(cur.get("symbols", [])) | set(config.MEGACAPS))
    kept, caps = [], {}
    for s in candidates:
        try:
            mc = yf.Ticker(s).fast_info.get("marketCap")
        except Exception:  # noqa: BLE001
            mc = None
        if mc:
            caps[s] = round(mc / 1e9, 1)
            if mc >= threshold_usd:
                kept.append(s)
    if not kept:
        raise RuntimeError("market caps unavailable; keeping existing list")
    _save(path, {
        "threshold_usd_bn": threshold_usd / 1e9,
        "refreshed_at": datetime.now(config.UTC).isoformat(timespec="seconds"),
        "symbols": kept,
        "market_cap_usd_bn": caps,
        "candidates": candidates,
    })
    return path


def refresh_all(year: int) -> list[str]:
    problems = []
    for name, fn in [("fomc", lambda: refresh_fomc(year)), ("auctions", refresh_auctions), ("large_caps", refresh_large_caps)]:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            problems.append(f"{name}: {e}")
    _, econ_problems = refresh_econ(year)
    return problems + econ_problems


# --- Loading for the brief ---------------------------------------------------------------

def load_fomc(year: int) -> list[dict]:
    meetings = []
    for y in (year, year + 1):
        meetings += _load(config.CALENDARS_DIR / f"fomc_{y}.json").get("meetings", [])
    return meetings


def load_econ(year: int) -> list[dict]:
    ev = []
    for y in (year, year + 1):
        ev += _load(config.CALENDARS_DIR / f"econ_{y}.json").get("events", [])
    return ev


def load_auctions() -> list[dict]:
    return _load(config.CALENDARS_DIR / "auctions.json").get("events", [])


def load_large_caps() -> list[str]:
    return _load(config.CALENDARS_DIR / "large_caps.json").get("symbols", list(config.MEGACAPS))
