"""Command line: `python -m digest run|straddle|journal|build|refresh-calendars`."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from digest import config, schedule, storage

log = logging.getLogger("digest")


def _gh_output(**kv) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def _skip(reason: str) -> int:
    print(reason)  # the one-line skip reason
    _gh_output(posted="false", reason=reason.replace("\n", " "))
    return 0


def _prior_verdict(paths: storage.PostPaths | None) -> str | None:
    if not paths:
        return None
    from digest.render import split_post

    fm, _ = split_post(paths.post.read_text())
    return f"{fm.get('date')} {fm.get('post_type')}: {fm['verdict']}" if fm.get("verdict") else None


def _brief_json(paths: storage.PostPaths | None) -> dict | None:
    """A stored brief of the current schema major version (older posts are ignored as context)."""
    if not paths or not paths.data("brief").exists():
        return None
    d = json.loads(paths.data("brief").read_text())
    major = config.SCHEMA_VERSION.split(".")[0]
    return d if str(d.get("meta", {}).get("schema_version", "")).split(".")[0] == major else None


def build_context(roots: list[Path], target: date, post_type: str) -> dict:
    """What earlier runs contribute to this one: the premarket straddle, the 09:35 ET print,
    the regime label from the earlier post today, and last session's mega-cap earnings."""
    ctx: dict = {}
    d = target.isoformat()
    if post_type != "premarket":
        pm = _brief_json(_find(roots, d, "premarket"))
        if pm:
            ctx["premarket_expected_move_0dte_pts"] = pm.get("vol", {}).get("expected_move_0dte_pts")
    s = storage.read_straddle(roots, d)
    if s:
        ctx["straddle_0935"] = s
    if post_type == "afternoon":
        mid = _brief_json(_find(roots, d, "midsession"))
        if mid and mid.get("regime"):
            ctx["prior_regime_label"] = mid["regime"]["label"]
    prev_d = schedule.prev_trading_day(target).isoformat()
    for pt in ("afternoon", "midsession", "premarket"):
        pb = _brief_json(_find(roots, prev_d, pt))
        if pb:
            ctx["prev_session_earnings"] = [e["name"] for e in pb.get("calendar", {}).get("events_today", []) if e.get("category") == "MEGACAP_EARNINGS"]
            break
    return ctx


def _find(roots: list[Path], d: str, post_type: str) -> storage.PostPaths | None:
    for r in roots:
        p = storage.latest_paths(r, d, post_type)
        if p:
            return p
    return None


def prior_post(roots: list[Path], target: date, post_type: str) -> storage.PostPaths | None:
    d = target.isoformat()
    if post_type == "premarket":
        return _find(roots, schedule.prev_trading_day(target).isoformat(), "afternoon")
    if post_type == "midsession":
        return _find(roots, d, "premarket")
    return _find(roots, d, "midsession") or _find(roots, d, "premarket")


def cmd_run(a) -> int:
    from digest import narrative, pipeline, render
    from digest.regime import load_rules

    now = datetime.now(config.PT)
    target = date.fromisoformat(a.date) if a.date else now.date()
    post_type = a.post

    if a.scheduled:
        ok, reason = schedule.check_window(post_type, now)
        if not ok:
            return _skip(reason)
        print(reason)
        if storage.latest_paths(config.ROOT, target.isoformat(), post_type):
            return _skip(f"skip {post_type}: already published for {target} (scheduled runs never add versions)")

    root = storage.output_root(write_to_dataset=(not a.dry_run) or a.write)
    lookup_roots = [root] + ([config.ROOT] if root != config.ROOT else [])
    as_of = pipeline.resolve_as_of(target, post_type, now)
    rules = load_rules()

    raw = pipeline.fetch_all(target, post_type, as_of)
    raw["context"] = build_context(lookup_roots, target, post_type)

    paths = storage.next_paths(root, target.isoformat(), post_type)
    brief = pipeline.build_brief(raw, rules, version=paths.version)

    if brief.meta.market_closed_mode and not pipeline.has_content(brief):
        msg = f"{target} is not a trading day and there is nothing to discuss (no events next session, futures not trading)."
        if not a.confirm_empty:
            if sys.stdin.isatty():
                if input(f"{msg} Publish anyway? [y/N] ").strip().lower() != "y":
                    return _skip(f"skip {post_type}: {msg} Not confirmed.")
            else:
                return _skip(f"skip {post_type}: {msg} Re-run with --confirm-empty (workflow input confirm_empty) to publish.")

    prev = prior_post(lookup_roots, target, post_type)
    prev_verdict = _prior_verdict(prev)

    files = {k: str(paths.data(k).relative_to(root)) for k in storage.KINDS}
    verdict = None
    if a.dry_run:
        body, mode, model = render.card(brief), "dry-run", None
        llm = {"skipped": "dry-run", "system": narrative.system_prompt(post_type), "user": narrative.user_message(brief, prev_verdict)}
    else:
        res = narrative.generate(brief, prev_verdict)
        llm = {"ok": res.ok, "error": res.error, "warnings": res.warnings, "request": res.request, "response": res.response,
               "previous_post": str(prev.post.relative_to(prev.root)) if prev else None}
        if res.ok:
            verdict = res.verdict
            body, mode = render.card(brief, res.verdict, res.text), "claude"
        else:
            log.warning("narrative unavailable: %s", res.error)
            body, mode = render.unavailable_body(brief), "unavailable"
        model = config.CLAUDE_MODEL

    fm = render.frontmatter(brief, mode, files, model, verdict)
    storage.write_json_new(paths.data("raw"), raw)
    storage.write_json_new(paths.data("brief"), json.loads(brief.model_dump_json()))
    storage.write_json_new(paths.data("llm"), llm)
    storage.write_new(paths.post, render.post_markdown(fm, body))
    print(f"wrote {paths.post.relative_to(config.ROOT)}: {brief.regime.label}, playbook {brief.playbook.live}, narrative: {mode}")
    _gh_output(posted="true", post_path=str(paths.post.relative_to(config.ROOT)))
    return 0


def cmd_straddle(a) -> int:
    """Record the day's 09:35 ET ATM straddle print: captured from the free chain, or typed in with --set."""
    from digest.fetch import market
    from digest.indicators.options import atm_straddle

    now = datetime.now(config.ET)
    target = date.fromisoformat(a.date) if a.date else now.date()
    d = target.isoformat()
    if a.set is not None:
        if a.set <= 0:
            print("--set needs a positive straddle price in SPX points")
            return 2
        rec = {"date": d, "pts": a.set, "time_et": a.time or "09:35", "source": "manual", "recorded_at": now.isoformat(timespec="seconds")}
        path = storage.write_straddle(config.ROOT, d, rec)
        print(f"recorded manual 09:35 ET straddle {a.set} for {d} in {path.relative_to(config.ROOT)}")
        _gh_output(posted="true", post_path=str(path.relative_to(config.ROOT)))
        return 0
    if target != now.date() or not schedule.is_trading_day(target):
        return _skip(f"skip straddle: {d} is not today's session (use --set PRICE to enter a print by hand)")
    hhmm = now.strftime("%H:%M")
    if a.scheduled:
        if not ("09:35" <= hhmm <= "10:00"):
            return _skip(f"skip straddle: {hhmm} ET is outside the 09:35–10:00 ET capture window")
        if any(json.loads(p.read_text()).get("source") != "manual" for p in storage.straddle_files(config.ROOT, d)):
            return _skip(f"skip straddle: already captured for {d}")
    res = market.fetch_option_chain(target)
    if not res.ok:
        return _skip(f"skip straddle: no free option chain ({res.error}); enter it with --set PRICE")
    chain = res.data
    scale = config.CHAIN_FALLBACK_SCALE if res.meta.get("fallback") else 1.0
    z = chain["chains"].get(chain.get("expiry_0dte"))
    spot = chain.get("underlying_price")
    k, px = atm_straddle(z["calls"], z["puts"], spot) if z and spot else (None, None)
    if not px:
        return _skip("skip straddle: the chain has no priced ATM straddle; enter it with --set PRICE")
    rec = {"date": d, "pts": round(px * scale, 2), "strike": k * scale, "spot": round(spot * scale, 2), "time_et": hhmm,
           "source": f"auto ({chain.get('symbol')} chain via yfinance" + (", strikes x10)" if scale != 1 else ")"),
           "recorded_at": now.isoformat(timespec="seconds")}
    path = storage.write_straddle(config.ROOT, d, rec)
    print(f"captured straddle {rec['pts']} at the {rec['strike']:g} strike, {hhmm} ET, in {path.relative_to(config.ROOT)}")
    _gh_output(posted="true", post_path=str(path.relative_to(config.ROOT)))
    return 0


def cmd_journal(a) -> int:
    from digest import journal

    print(journal.summary_text(Path(a.file) if a.file else config.JOURNAL_PATH))
    return 0


def cmd_build(a) -> int:
    from digest import build

    root = Path(a.root).resolve() if a.root else config.ROOT
    out = Path(a.out).resolve() if a.out else config.ROOT / "site"
    n = build.build_site(root, out)
    print(f"built {out} from {root / 'posts'} ({n} posts)")
    return 0


def cmd_refresh(a) -> int:
    from digest import calendars

    problems = calendars.refresh_all(a.year)
    for p in problems:
        print(f"warning: {p}")
    print("calendars refreshed" + (f" with {len(problems)} warnings" if problems else ""))
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=os.environ.get("DIGEST_LOG", "WARNING"), format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="digest", description="SPX 0DTE daily digest (read-only).")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="fetch, compute, write one post")
    r.add_argument("--post", choices=config.POST_TYPES, required=True)
    r.add_argument("--date", help="YYYY-MM-DD (default: today PT). Past dates replay as of the slot time; no option chain.")
    r.add_argument("--dry-run", action="store_true", help="skip the Claude call; render the brief as bullets; write to out/")
    r.add_argument("--write", action="store_true", help="with --dry-run, write into posts/ and data/ instead of out/")
    r.add_argument("--scheduled", action="store_true", help="cron mode: exit unless now is inside this post's window")
    r.add_argument("--confirm-empty", action="store_true", help="publish on a non-trading day even with nothing to discuss")
    r.set_defaults(fn=cmd_run)

    st = sub.add_parser("straddle", help="record the 09:35 ET ATM straddle print (auto capture, or --set by hand)")
    st.add_argument("--set", type=float, help="straddle price in SPX points, typed in by hand")
    st.add_argument("--time", help="HH:MM ET of a hand-entered print (default 09:35)")
    st.add_argument("--date", help="YYYY-MM-DD (default: today ET); past dates need --set")
    st.add_argument("--scheduled", action="store_true", help="cron mode: only between 09:35 and 10:00 ET, once per day")
    st.set_defaults(fn=cmd_straddle)

    j = sub.add_parser("journal", help="summarise journal/trades.csv: expectancy by playbook and entry window")
    j.add_argument("--file", help="CSV path (default: journal/trades.csv)")
    j.set_defaults(fn=cmd_journal)

    b = sub.add_parser("build", help="render the static site from posts/")
    b.add_argument("--root", help="dataset root containing posts/ and data/ (default: repo; use 'out' for dry runs)")
    b.add_argument("--out", help="output directory (default: site/)")
    b.set_defaults(fn=cmd_build)

    c = sub.add_parser("refresh-calendars", help="refresh calendars/*.json from official sources")
    c.add_argument("--year", type=int, default=datetime.now(config.PT).year)
    c.set_defaults(fn=cmd_refresh)

    a = p.parse_args(argv)
    return a.fn(a)
