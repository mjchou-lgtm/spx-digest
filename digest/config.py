"""Static configuration: paths, tickers, post slots, model settings.

This package is read-only by design: it contains no brokerage clients, no
order models and no credentials other than ANTHROPIC_API_KEY and FRED_API_KEY.
"""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

SCHEMA_VERSION = "1.0"

CALENDARS_DIR = ROOT / "calendars"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
REGIME_RULES_PATH = ROOT / "regime_rules.yaml"
FORBIDDEN_PHRASES_PATH = ROOT / "forbidden_phrases.txt"
DOCS_DIR = ROOT / "docs"

POST_TYPES = ("premarket", "midsession", "afternoon")

# Scheduled publish time (Pacific) per post type on a normal session.
POST_TIMES_PT = {
    "premarket": (5, 45),
    "midsession": (9, 30),
    "afternoon": (11, 45),
}
# On an early-close day the afternoon post moves to this many minutes before the close.
EARLY_CLOSE_AFTERNOON_LEAD_MIN = 60
# A scheduled run is accepted if it starts between EARLY_TOLERANCE before and
# LATE_TOLERANCE after the slot (GitHub cron routinely starts late).
WINDOW_EARLY_TOLERANCE_MIN = 5
WINDOW_LATE_TOLERANCE_MIN = 40

# --- Tickers -----------------------------------------------------------------
SPX = "^GSPC"
FUTURES = ["ES=F", "NQ=F", "RTY=F"]
VOL = ["^VIX", "^VIX9D", "^VIX3M", "^VIX6M", "^VVIX", "^SKEW"]
RATES = ["^TNX", "^FVX", "^IRX"]
MACRO = ["DX-Y.NYB", "CL=F", "GC=F"]
ETFS = ["SPY", "RSP", "QQQ", "IWM"]
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"]
MEGACAPS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO"]

DAILY_TICKERS = [SPX, *FUTURES, *VOL, *RATES, *MACRO, *ETFS, *SECTORS, *MEGACAPS]
# 5-min bars (with pre/post) — only what the indicators actually use.
INTRADAY_TICKERS = [SPX, "ES=F", "NQ=F", "RTY=F", "^VIX", "SPY", "RSP", "QQQ", "IWM", *SECTORS, *MEGACAPS]

CHAIN_PRIMARY = "^SPX"
CHAIN_FALLBACK = "SPY"
CHAIN_FALLBACK_SCALE = 10.0

FRED_SERIES = ["DGS10", "DGS2", "T10Y2Y", "DFF", "VIXCLS"]

RSS_FEEDS = {
    "CNBC Markets": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "MarketWatch Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    # BLS news-release RSS returns 403 to non-browser clients (bot protection);
    # we do not work around it. TODO: re-enable if BLS opens the feed.
}
HEADLINES_MAX = 10

CBOE_DAILY_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options"
FED_CALENDAR_URL = "https://www.federalreserve.gov/json/calendar.json"
TREASURY_UPCOMING_URL = "https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
FRED_BASE = "https://api.stlouisfed.org/fred"

HTTP_USER_AGENT = "spx-digest/0.1 (read-only market digest)"
HTTP_TIMEOUT_S = 20
RETRIES = 3

# --- Narrative -----------------------------------------------------------------
CLAUDE_MODEL = os.environ.get("DIGEST_CLAUDE_MODEL", "claude-sonnet-5-5")
# Thinking tokens count against max_tokens; the prompt caps the prose at ~700 tokens.
CLAUDE_MAX_TOKENS = 3000
CLAUDE_EFFORT = "low"

SITE_TITLE = "SPX 0DTE Digest"
SITE_BASE_URL = os.environ.get("DIGEST_SITE_URL", "")  # e.g. https://<user>.github.io/spx-digest


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def fred_key() -> str | None:
    return os.environ.get("FRED_API_KEY") or None
