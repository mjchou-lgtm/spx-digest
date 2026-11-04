from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from digest import config

log = logging.getLogger("digest.fetch")


@dataclass
class FetchResult:
    source: str
    fetched_at: str
    ok: bool
    data: Any = None
    error: str | None = None
    meta: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_with_retry(
    source: str,
    fn: Callable[[], Any],
    retries: int = config.RETRIES,
    backoff_s: float = 1.5,
    meta: dict | None = None,
) -> FetchResult:
    """Run fn() with retries. Never raises: a failure returns ok=False, data=None."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            data = fn()
            return FetchResult(source=source, fetched_at=now_utc_iso(), ok=True, data=data, meta=meta or {})
        except Exception as e:  # noqa: BLE001 — degrade gracefully, record the error
            last_err = f"{type(e).__name__}: {e}"
            log.warning("fetch %s attempt %d/%d failed: %s", source, attempt, retries, last_err)
            if attempt < retries:
                time.sleep(backoff_s * attempt)
    return FetchResult(source=source, fetched_at=now_utc_iso(), ok=False, data=None, error=last_err, meta=meta or {})


def http_get(url: str, params: dict | None = None, timeout: float = config.HTTP_TIMEOUT_S) -> requests.Response:
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": config.HTTP_USER_AGENT})
    r.raise_for_status()
    return r
