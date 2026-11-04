import ast
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from digest import config, schedule, storage
from digest.brief import Brief
from digest.schema_doc import render as render_schema_doc
from digest.schema_doc import rows as schema_rows
from digest.strategies import REGISTRY, OpeningRangeContext, Strategy

ROOT = Path(__file__).resolve().parent.parent
PT = config.PT


# --- brief schema ---------------------------------------------------------------

def test_brief_roundtrips_through_pydantic(brief_mid):
    again = Brief.model_validate_json(brief_mid.model_dump_json())
    assert again == brief_mid
    assert again.meta.schema_version == config.SCHEMA_VERSION


def test_brief_rejects_unknown_fields(brief_mid):
    d = json.loads(brief_mid.model_dump_json())
    d["levels"]["made_up_field"] = 1
    with pytest.raises(ValidationError):
        Brief(**d)


def test_brief_sections_are_flat_and_snake_case(brief_mid):
    d = json.loads(brief_mid.model_dump_json())
    for sec, fields in d.items():
        for k, v in fields.items():
            assert k == k.lower() and " " not in k
            if isinstance(v, dict):
                assert all(not isinstance(x, (dict, list)) for x in v.values()), f"{sec}.{k} nests too deep"
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        assert all(not isinstance(y, (dict, list)) for y in x.values())


def test_committed_briefs_validate():
    for p in (ROOT / "data").rglob("*.brief.json"):
        Brief.model_validate_json(p.read_text())


def test_schema_doc_is_complete_and_current():
    assert all(desc for _, _, _, desc in schema_rows()), "every brief field needs a description in schema_doc.D"
    assert (ROOT / "docs" / "brief-schema.md").read_text() == render_schema_doc(), "run: python -m digest.schema_doc"


# --- schedule ---------------------------------------------------------------------

def test_holiday_and_weekend_are_not_trading_days():
    assert not schedule.is_trading_day(date(2026, 11, 26))  # Thanksgiving
    assert not schedule.is_trading_day(date(2026, 11, 7))   # Saturday
    assert schedule.is_trading_day(date(2026, 11, 4))


def test_early_close_moves_afternoon_slot():
    s = schedule.session(date(2026, 11, 27))  # day after Thanksgiving
    assert s.early_close
    slot = schedule.scheduled_time_pt("afternoon", date(2026, 11, 27))
    assert slot.strftime("%H:%M") == "09:00"  # 13:00 ET close -> 10:00 PT, minus 60 min
    assert schedule.scheduled_time_pt("afternoon", date(2026, 11, 4)).strftime("%H:%M") == "11:45"


@pytest.mark.parametrize("hhmm,ok", [("05:40", True), ("05:45", True), ("06:25", True), ("06:30", False), ("04:45", False)])
def test_window(hhmm, ok):
    h, m = map(int, hhmm.split(":"))
    res, reason = schedule.check_window("premarket", datetime(2026, 11, 4, h, m, tzinfo=PT))
    assert res is ok and reason


def test_both_dst_crons_only_one_runs():
    # PST date: 13:45 UTC = 05:45 PST (runs); 12:45 UTC = 04:45 PST (skips).
    utc = config.UTC
    assert schedule.check_window("premarket", datetime(2026, 11, 4, 13, 45, tzinfo=utc))[0]
    assert not schedule.check_window("premarket", datetime(2026, 11, 4, 12, 45, tzinfo=utc))[0]
    # PDT date: 12:45 UTC = 05:45 PDT (runs); 13:45 UTC = 06:45 PDT (skips).
    assert schedule.check_window("premarket", datetime(2026, 6, 3, 12, 45, tzinfo=utc))[0]
    assert not schedule.check_window("premarket", datetime(2026, 6, 3, 13, 45, tzinfo=utc))[0]


def test_skip_reason_on_holiday():
    ok, reason = schedule.check_window("midsession", datetime(2026, 11, 26, 9, 30, tzinfo=PT))
    assert not ok and "not an NYSE trading day" in reason and "\n" not in reason


# --- storage ------------------------------------------------------------------------

def test_versions_never_overwrite(tmp_path):
    p1 = storage.next_paths(tmp_path, "2026-11-04", "premarket")
    assert p1.version == 1 and p1.post.name == "premarket.md"
    storage.write_new(p1.post, "x")
    with pytest.raises(FileExistsError):
        storage.write_new(p1.post, "y")
    p2 = storage.next_paths(tmp_path, "2026-11-04", "premarket")
    assert p2.version == 2 and p2.post.name == "premarket.2.md" and p2.data("brief").name == "premarket.2.brief.json"
    storage.write_new(p2.post, "z")
    assert storage.latest_paths(tmp_path, "2026-11-04", "premarket").version == 2
    # A crash after writing data but before the post still bumps the version.
    storage.write_json_new(storage.next_paths(tmp_path, "2026-11-04", "premarket").data("raw"), {})
    assert storage.next_paths(tmp_path, "2026-11-04", "premarket").version == 4


# --- site build -------------------------------------------------------------------

def test_build_site_from_fixture(tmp_path, brief_mid):
    from digest import build, render

    root = tmp_path / "ds"
    paths = storage.next_paths(root, brief_mid.meta.date, brief_mid.meta.post_type)
    storage.write_json_new(paths.data("brief"), json.loads(brief_mid.model_dump_json()))
    files = {k: str(paths.data(k).relative_to(root)) for k in storage.KINDS}
    fm = render.frontmatter(brief_mid, "unavailable", files, None)
    storage.write_new(paths.post, render.post_markdown(fm, render.table_body(brief_mid, "test")))
    out = tmp_path / "site"
    assert build.build_site(root, out) == 1
    for f in ["index.html", "archive/index.html", "data/index.html", "about/index.html", "feed.xml", "api/latest.json",
              "posts/2026-11-04/midsession.html", "static/style.css"]:
        assert (out / f).exists(), f
    page = (out / "posts/2026-11-04/midsession.html").read_text()
    assert "Narrative unavailable" in page and "Indicator brief" in page and "Data quality" in page
    assert "▲ TREND_UP" in page.replace("<span aria-hidden=\"true\">▲</span> ", "▲ ")  # icon + label, not colour alone
    latest = json.loads((out / "api/latest.json").read_text())
    assert latest["posts"]["midsession"]["regime"] == brief_mid.regime.label
    assert latest["posts"]["midsession"]["brief"]["meta"]["schema_version"] == config.SCHEMA_VERSION


# --- strategies + read-only guarantees ------------------------------------------------

def test_opening_range_context(brief_mid, brief_pre):
    s = OpeningRangeContext()
    assert isinstance(s, Strategy) and s in REGISTRY or isinstance(REGISTRY[0], OpeningRangeContext)
    r = s.evaluate(brief_mid)
    assert r.applicability == "applicable" and any(brief_mid.intraday.spot_vs_or in c for c in r.conditions_met)
    assert s.evaluate(brief_pre).applicability == "unknown"


BANNED_IMPORTS = {"alpaca", "ib_insync", "ibapi", "robin_stocks", "tda", "schwab", "tastytrade", "ccxt", "webull", "tradier"}


def test_codebase_has_no_execution_paths():
    """Read-only forever: no broker SDKs, no order verbs in code."""
    for py in (ROOT / "digest").rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + ([node.module] if getattr(node, "module", None) else [])
                for n in names:
                    assert n.split(".")[0] not in BANNED_IMPORTS, f"{py}: imports {n}"
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                low = node.name.lower()
                assert not any(v in low for v in ("place_order", "submit_order", "cancel_order", "modify_order")), f"{py}: {node.name}"
    env_names = (ROOT / ".env.example").read_text()
    assert set(line.split("=")[0] for line in env_names.splitlines() if "=" in line) == {"ANTHROPIC_API_KEY", "FRED_API_KEY"}
