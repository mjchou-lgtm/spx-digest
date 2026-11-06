import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


def _replay(raw: dict, post_type: str, as_of: str, context: dict | None = None) -> dict:
    """The same real payload replayed as of another slot (bars after as_of are trimmed by the pipeline)."""
    r = json.loads(json.dumps(raw))
    r.update(post_type=post_type, as_of=as_of, context=context or {})
    return r


def _build(raw, generated_at):
    from digest.pipeline import build_brief

    return build_brief(raw, generated_at=generated_at)


# 2026-11-06: live capture at 11:25 ET with the real ^SPX chain. Open inside prior value, VWAP crossed twice: balance.
@pytest.fixture(scope="session")
def raw_mid():
    return json.loads((FIX / "2026-11-06_midsession.raw.json").read_text())


@pytest.fixture(scope="session")
def raw_pre(raw_mid):
    return _replay(raw_mid, "premarket", "2026-11-06T06:15:00-08:00")


@pytest.fixture(scope="session")
def brief_mid(raw_mid):
    return _build(raw_mid, "2026-11-06T16:25:00+00:00")


@pytest.fixture(scope="session")
def brief_pre(raw_pre):
    return _build(raw_pre, "2026-11-06T14:15:00+00:00")


# 2026-11-05: replay (no option chain). Open below prior value, VWAP never crossed: trend_down.
@pytest.fixture(scope="session")
def raw_td_aft():
    return json.loads((FIX / "2026-11-05_afternoon.raw.json").read_text())


@pytest.fixture(scope="session")
def brief_td_mid(raw_td_aft):
    return _build(_replay(raw_td_aft, "midsession", "2026-11-05T07:45:00-08:00"), "2026-11-05T15:45:00+00:00")


@pytest.fixture(scope="session")
def brief_td_aft(raw_td_aft):
    return _build(_replay(raw_td_aft, "afternoon", "2026-11-05T11:15:00-08:00", {"prior_regime_label": "trend_down"}), "2026-11-05T19:15:00+00:00")
