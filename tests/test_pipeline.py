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
    """Briefs of the current major schema version must validate; 1.x briefs stay in the archive as written."""
    major = config.SCHEMA_VERSION.split(".")[0]
    for p in (ROOT / "data").rglob("*.brief.json"):
        d = json.loads(p.read_text())
        if d["meta"]["schema_version"].split(".")[0] == major:
            Brief.model_validate(d)


def test_schema_is_v2_without_dealer_gamma(brief_mid):
    assert config.SCHEMA_VERSION.split(".")[0] == "2"
    assert "gamma" not in brief_mid.model_dump_json().replace("Dealer gamma", "") and "gex_method" not in brief_mid.model_dump_json()
    assert brief_mid.positioning.gex_vendor_url is None


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
    assert schedule.scheduled_time_pt("afternoon", date(2026, 11, 4)).strftime("%H:%M") == "11:15"


def test_slots_are_0915_1045_1415_et():
    d = date(2026, 11, 4)
    et = [schedule.scheduled_time_pt(p, d).astimezone(config.ET).strftime("%H:%M") for p in config.POST_TYPES]
    assert et == ["09:15", "10:45", "14:15"]


@pytest.mark.parametrize("hhmm,ok", [("06:10", True), ("06:15", True), ("06:55", True), ("07:00", False), ("05:15", False)])
def test_window(hhmm, ok):
    h, m = map(int, hhmm.split(":"))
    res, reason = schedule.check_window("premarket", datetime(2026, 11, 4, h, m, tzinfo=PT))
    assert res is ok and reason


def test_both_dst_crons_only_one_runs():
    # PST date: 14:15 UTC = 06:15 PST (runs); 13:15 UTC = 05:15 PST (skips).
    utc = config.UTC
    assert schedule.check_window("premarket", datetime(2026, 11, 4, 14, 15, tzinfo=utc))[0]
    assert not schedule.check_window("premarket", datetime(2026, 11, 4, 13, 15, tzinfo=utc))[0]
    # PDT date: 13:15 UTC = 06:15 PDT (runs); 14:15 UTC = 07:15 PDT (skips).
    assert schedule.check_window("premarket", datetime(2026, 6, 3, 13, 15, tzinfo=utc))[0]
    assert not schedule.check_window("premarket", datetime(2026, 6, 3, 14, 15, tzinfo=utc))[0]


def test_workflow_crons_match_the_slots():
    import re

    import yaml

    for post, (hh, mm) in config.POST_TIMES_PT.items():
        wf = (ROOT / ".github" / "workflows" / f"{post}.yml").read_text()
        crons = re.findall(r'cron: "(\d+) (\d+) \* \* 1-5"', wf)
        want = {(str(mm), str(hh + 7)), (str(mm), str(hh + 8))}  # PDT and PST
        assert want <= set(crons), (post, crons)
    st = yaml.safe_load((ROOT / ".github" / "workflows" / "straddle.yml").read_text())
    assert {c["cron"] for c in st[True]["schedule"]} == {"35 13 * * 1-5", "35 14 * * 1-5"}  # 09:35 ET in EDT / EST
    assert "workflow_dispatch" in st[True]


def test_no_midsession_on_early_close():
    ok, reason = schedule.check_window("midsession", datetime(2026, 11, 27, 7, 45, tzinfo=PT))
    assert not ok and "early-close" in reason
    assert schedule.check_window("afternoon", datetime(2026, 11, 27, 9, 0, tzinfo=PT))[0]
    assert schedule.check_window("premarket", datetime(2026, 11, 27, 6, 15, tzinfo=PT))[0]
    assert schedule.posts_on("midsession", date(2026, 11, 4))


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

def test_build_site_from_fixture(tmp_path, brief_mid, monkeypatch):
    from datetime import datetime

    from digest import build, render

    class _Nov6(datetime):  # the home page shows today's slots, so build as of the fixture's day
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 6, 8, 45, tzinfo=tz)

    monkeypatch.setattr(build, "datetime", _Nov6)
    root = tmp_path / "ds"
    paths = storage.next_paths(root, brief_mid.meta.date, brief_mid.meta.post_type)
    storage.write_json_new(paths.data("brief"), json.loads(brief_mid.model_dump_json()))
    files = {k: str(paths.data(k).relative_to(root)) for k in storage.KINDS}
    fm = render.frontmatter(brief_mid, "unavailable", files, None)
    storage.write_new(paths.post, render.post_markdown(fm, render.unavailable_body(brief_mid)))
    out = tmp_path / "site"
    assert build.build_site(root, out) == 1
    for f in ["index.html", "archive/index.html", "data/index.html", "about/index.html", "feed.xml", "api/latest.json",
              "posts/2026-11-06/midsession.html", "static/style.css", "run/index.html", "static/run.js", "concepts/index.html",
              "concepts/daily-structure.html", "concepts/premium.html", "concepts/volume-profile.html", "concepts/edge.html", "concepts/rules.html",
              "concepts/glossary.html"]:
        assert (out / f).exists(), f
    page = (out / "posts/2026-11-06/midsession.html").read_text()
    assert "Narrative unavailable" in page and "Indicator brief" in page and "Data quality" in page
    assert "↔ balance" in page.replace("<span aria-hidden=\"true\">↔</span> ", "↔ ")  # icon + label, not colour alone
    assert 'href="../../concepts/premium.html#theta"' in page
    assert '<section class="verdict-box"><h2>Verdict</h2>' in page and page.index("verdict-box") < page.index("<h2>Technical</h2>") < page.index("<h2>News / macro</h2>")
    home = (out / "index.html").read_text()
    assert "Range-bound day (balance); playbook: none" in home and '<ul class="watch">' in home
    assert "Early setup: not live, option prices are high on a range-bound day" in home and "In plain terms: buyers and sellers roughly agree" in home
    prem = (out / "concepts/premium.html").read_text()
    assert 'id="theta"' in prem and "10:30 ET / 07:30 PT" in prem and "92%" in prem and "28%" in prem
    rules = (out / "concepts/rules.html").read_text()
    assert "not set" in rules and "counter-trend on gap-and-go" in rules and "{{" not in rules
    latest = json.loads((out / "api/latest.json").read_text())
    assert latest["posts"]["midsession"]["regime"] == brief_mid.regime.label
    assert latest["posts"]["midsession"]["brief"]["meta"]["schema_version"] == config.SCHEMA_VERSION
    assert latest["posts"]["midsession"]["playbook"] == "none" and latest["posts"]["midsession"]["verdict"]


def test_archive_still_renders_schema_1_posts(tmp_path):
    """The 2026-11-04 posts were written under schema 1.0 and are never rewritten."""
    from digest import build

    out = tmp_path / "site"
    n = build.build_site(ROOT, out)
    assert n >= 3 and (out / "posts/2026-11-04/premarket.html").exists()
    assert "TREND_UP" in (out / "posts/2026-11-04/premarket.html").read_text()


# --- 09:35 ET straddle print ---------------------------------------------------------

def test_straddle_print_is_append_only_and_manual_wins(tmp_path):
    d = "2026-11-06"
    assert storage.read_straddle([tmp_path], d) is None
    storage.write_straddle(tmp_path, d, {"pts": 60.0, "time_et": "09:37", "source": "auto (^SPX chain via yfinance)"})
    storage.write_straddle(tmp_path, d, {"pts": 55.0, "time_et": "09:52", "source": "auto (^SPX chain via yfinance)"})
    assert storage.read_straddle([tmp_path], d)["pts"] == 60.0  # first automatic capture
    storage.write_straddle(tmp_path, d, {"pts": 61.5, "time_et": "09:35", "source": "manual"})
    storage.write_straddle(tmp_path, d, {"pts": 62.0, "time_et": "09:35", "source": "manual"})
    assert storage.read_straddle([tmp_path], d)["pts"] == 62.0  # latest manual entry
    assert [p.name for p in storage.straddle_files(tmp_path, d)] == [
        "straddle_0935.json", "straddle_0935.2.json", "straddle_0935.3.json", "straddle_0935.4.json"]


def test_straddle_cli_manual_entry(tmp_path, monkeypatch, capsys):
    from digest import cli

    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert cli.main(["straddle", "--set", "58.4", "--date", "2026-11-05"]) == 0
    assert storage.read_straddle([tmp_path], "2026-11-05") | {"recorded_at": None} == {
        "date": "2026-11-05", "pts": 58.4, "time_et": "09:35", "source": "manual", "recorded_at": None}
    assert cli.main(["straddle", "--set", "-1"]) == 2
    assert cli.main(["straddle", "--date", "2026-11-05"]) == 0 and "use --set" in capsys.readouterr().out


def test_run_context_reads_earlier_posts(tmp_path, brief_td_mid):
    from digest import cli, render

    paths = storage.next_paths(tmp_path, "2026-11-05", "midsession")
    storage.write_json_new(paths.data("brief"), json.loads(brief_td_mid.model_dump_json()))
    storage.write_new(paths.post, render.post_markdown(render.frontmatter(brief_td_mid, "dry-run", {}, None), render.card(brief_td_mid)))
    storage.write_straddle(tmp_path, "2026-11-05", {"pts": 70.0, "time_et": "09:35", "source": "manual"})
    ctx = cli.build_context([tmp_path], date(2026, 11, 5), "afternoon")
    assert ctx["prior_regime_label"] == "trend_down" and ctx["straddle_0935"]["pts"] == 70.0
    assert cli._prior_verdict(cli.prior_post([tmp_path], date(2026, 11, 5), "afternoon")).endswith("Downtrend day (trend_down); playbook: early")
    # Schema 1.x briefs are not used as context.
    assert cli.build_context([ROOT], date(2026, 11, 4), "afternoon").get("prior_regime_label") is None


# --- calendar extras, time formatting, journal ----------------------------------------------

def test_ff_events_skip_duplicates_of_official_calendars():
    from digest.indicators.events import _ev, ff_events
    from digest.regime import load_rules

    rules = load_rules()
    d = date(2026, 11, 6)
    ff = [{"date": "2026-11-06", "time_et": "08:30", "title": "Non-Farm Employment Change", "impact": "High"},
          {"date": "2026-11-06", "time_et": "10:00", "title": "Prelim UoM Consumer Sentiment", "impact": "High"},
          {"date": "2026-11-05", "time_et": "08:30", "title": "Unemployment Claims", "impact": "High"}]
    have = [_ev("2026-11-06", "08:30", "Employment Situation", "NFP", rules)]
    out = ff_events(ff, d, have, rules)
    assert [e["name"] for e in out] == ["Prelim UoM Consumer Sentiment"]
    assert out[0]["premium_relevance"] == "high" and out[0]["url"].startswith("https://www.forexfactory.com")
    assert len(ff_events(ff, d, [], rules)) == 2
    assert have[0]["url"].startswith("https://www.bls.gov")


def test_times_in_both_zones():
    from digest.timefmt import both, num, tidy, with_pt

    assert both("10:30") == "10:30 ET / 07:30 PT" and both(None) == "time n/a"
    assert with_pt("window 14:30–15:45 ET, stop 13:00 ET") == "window 14:30–15:45 ET / 11:30–12:45 PT, stop 13:00 ET / 10:00 PT"
    assert with_pt(both("09:35")) == both("09:35")  # idempotent
    assert num(7400.0) == "7400" and num(51.65) == "51.65" and num(None) == "n/a"
    assert tidy("value (7693.0–7711.0), 0.05") == "value (7693–7711), 0.05"


def test_journal_reports_expectancy_only_from_30_rows(tmp_path):
    import csv

    from digest import journal

    assert (ROOT / "journal" / "trades.csv").read_text().strip().split(",") == journal.FIELDS
    f = tmp_path / "trades.csv"
    rows = [{"date": "2026-11-05", "playbook": "early", "entry_time": "10:15" if i % 2 else "11:20", "pnl_r": "1.5" if i % 3 else "-1", "pnl_usd": "150" if i % 3 else "-100"}
            for i in range(30)]
    rows += [{"date": "2026-11-05", "playbook": "late", "entry_time": "14:40", "pnl_r": "2", "pnl_usd": "200"}] * 5
    with open(f, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=journal.FIELDS)
        w.writeheader()
        w.writerows(rows)
    text = journal.summary_text(f)
    assert "late: 5 rows; expectancy is reported from 30 rows (25 to go)" in text
    assert "early:" in text and "10:00–11:00 ET" in text and "11:00–12:00 ET" in text
    e = journal.expectancy(journal.load(f)[:30])
    assert e["n"] == 30 and e["win_rate_pct"] == pytest.approx(100 * 20 / 30)
    assert e["expectancy_r"] == pytest.approx((20 * 1.5 - 10) / 30)
    assert journal.window_of("15:50") == "other"


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
