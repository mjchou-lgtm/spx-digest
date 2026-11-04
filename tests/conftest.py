import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def raw_mid():
    return json.loads((FIX / "2026-11-04_midsession.raw.json").read_text())


@pytest.fixture(scope="session")
def raw_pre(raw_mid):
    """Same real payload replayed as of the 05:45 PT premarket slot (bars after that are trimmed)."""
    r = json.loads(json.dumps(raw_mid))
    r["post_type"] = "premarket"
    r["as_of"] = "2026-11-04T05:45:00-08:00"
    return r


@pytest.fixture(scope="session")
def brief_mid(raw_mid):
    from digest.pipeline import build_brief

    return build_brief(raw_mid, generated_at="2026-11-04T17:45:00+00:00")


@pytest.fixture(scope="session")
def brief_pre(raw_pre):
    from digest.pipeline import build_brief

    return build_brief(raw_pre, generated_at="2026-11-04T13:45:00+00:00")
