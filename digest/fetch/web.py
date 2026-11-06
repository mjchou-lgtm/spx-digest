"""Non-yfinance public sources: CBOE daily stats, FRED, RSS headlines, Fed calendar, Treasury auctions."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from digest import config
from digest.fetch.base import FetchResult, fetch_with_retry, http_get, now_utc_iso


def fetch_cboe_daily(stats_date: date) -> FetchResult:
    """CBOE daily market statistics (put/call ratios) for a completed session.

    The legacy CBOE CSV downloads were retired; this is the JSON that backs
    cboe.com/us/options/market_statistics/daily/.
    """
    url = config.CBOE_DAILY_URL.format(date=stats_date.isoformat())

    def run():
        d = http_get(url).json()
        ratios = {r["name"]: r["value"] for r in d.get("ratios", [])}
        if not ratios:
            raise RuntimeError("no ratios in CBOE payload")
        return {"date": stats_date.isoformat(), "ratios": ratios}

    return fetch_with_retry("cboe:daily_options", run, meta={"url": url})


def fetch_fred(series: list[str] = config.FRED_SERIES) -> FetchResult:
    key = config.fred_key()
    if not key:
        return FetchResult(source="fred", fetched_at=now_utc_iso(), ok=False, error="FRED_API_KEY not set")

    def run():
        out = {}
        for s in series:
            r = http_get(
                f"{config.FRED_BASE}/series/observations",
                params={"series_id": s, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 30},
            ).json()
            out[s] = [{"date": o["date"], "value": o["value"]} for o in r.get("observations", [])]
        return out

    return fetch_with_retry("fred", run)


def fetch_fred_release_dates(release_id: int, year: int) -> list[str]:
    """Scheduled release dates (FRED release calendar). Raises on failure."""
    key = config.fred_key()
    if not key:
        raise RuntimeError("FRED_API_KEY not set")
    r = http_get(
        f"{config.FRED_BASE}/release/dates",
        params={
            "release_id": release_id,
            "api_key": key,
            "file_type": "json",
            "realtime_start": f"{year}-01-01",
            "realtime_end": f"{year}-12-31",
            "include_release_dates_with_no_data": "true",
            "limit": 1000,
        },
    ).json()
    return sorted({d["date"] for d in r.get("release_dates", []) if d["date"].startswith(str(year))})


def _entry_time(e) -> str | None:
    for k in ("published", "updated"):
        v = e.get(k)
        if v:
            try:
                return parsedate_to_datetime(v).astimezone(timezone.utc).isoformat(timespec="seconds")
            except (TypeError, ValueError):
                pass
    return None


def fetch_headlines() -> FetchResult:
    """Titles + timestamps only (no article bodies), newest first across feeds."""

    def run():
        items, failed = [], []
        for name, url in config.RSS_FEEDS.items():
            res = fetch_with_retry(f"rss:{name}", lambda u=url: feedparser.parse(http_get(u).content), retries=2)
            if not res.ok or not res.data.entries:
                failed.append(name)
                continue
            for e in res.data.entries[:25]:
                title = (e.get("title") or "").strip()
                if title:
                    items.append({"title": title, "source": name, "published_utc": _entry_time(e)})
        if not items:
            raise RuntimeError("all RSS feeds failed")
        # Round-robin across feeds (newest first within each) so one busy feed cannot fill the top 10.
        by_feed: dict[str, list] = {}
        for it in sorted(items, key=lambda x: x["published_utc"] or "", reverse=True):
            by_feed.setdefault(it["source"], []).append(it)
        mixed = []
        while any(by_feed.values()):
            for q in by_feed.values():
                if q:
                    mixed.append(q.pop(0))
        return {"items": mixed, "failed_feeds": failed}

    return fetch_with_retry("rss", run, retries=1)


def fetch_fed_calendar() -> FetchResult:
    """federalreserve.gov calendar JSON (FOMC, minutes, speeches, testimony). Times are ET."""

    def run():
        raw = http_get(config.FED_CALENDAR_URL).content.decode("utf-8-sig")
        events = json.loads(raw).get("events", [])
        return [
            {k: e.get(k) for k in ("title", "type", "month", "days", "time", "location", "description")}
            for e in events
        ]

    return fetch_with_retry("fed:calendar", run)


def fetch_treasury_upcoming() -> FetchResult:
    def run():
        rows = http_get(config.TREASURY_UPCOMING_URL).json()
        return [
            {
                "security_type": r.get("securityType"),
                "security_term": r.get("securityTerm"),
                "auction_date": (r.get("competitiveAuctionCloseDate") or r.get("auctionDate") or "")[:10] or None,
                "close_time_et": r.get("competitiveAuctionCloseTime"),
                "offering_amount": r.get("offeringAmount"),
                "cusip": r.get("cusip"),
            }
            for r in rows
        ]

    return fetch_with_retry("treasury:upcoming", run)


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def fetch_ff_calendar() -> FetchResult:
    """ForexFactory's public weekly calendar feed: USD events with impact and ET time."""
    def run():
        rows = http_get(config.FF_CALENDAR_URL).json()
        out = []
        for r in rows:
            if r.get("country") != "USD" or r.get("impact") not in ("High", "Medium"):
                continue
            try:
                ts = datetime.fromisoformat(r["date"]).astimezone(config.ET)
            except (KeyError, ValueError):
                continue
            out.append({"date": ts.date().isoformat(), "time_et": ts.strftime("%H:%M"), "title": r.get("title", "").strip(), "impact": r["impact"]})
        return out

    return fetch_with_retry("forexfactory:calendar", run, retries=1, meta={"url": config.FF_CALENDAR_URL})
