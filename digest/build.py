"""Static site: index (today's three slots), post pages, archive, /data/, /about, feed.xml, api/latest.json."""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from email.utils import format_datetime
from html import escape
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from digest import config, schedule
from digest.render import LABEL_ICON, SECTION_TITLES, fmt, split_post

MD_EXT = ["tables", "sane_lists"]


@dataclass
class Post:
    date: str
    post_type: str
    version: int
    stem: str
    fm: dict
    body_md: str
    brief: dict | None
    url: str  # relative to site root
    versions: list[int] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.fm.get("regime", "NO_TRADE")

    @property
    def icon(self) -> str:
        return LABEL_ICON.get(self.label, "•")

    @property
    def time_pt(self) -> str:
        try:
            return datetime.fromisoformat(self.fm["generated_at"]).astimezone(config.PT).strftime("%H:%M")
        except (KeyError, TypeError, ValueError):
            return ""


def load_posts(root: Path) -> list[Post]:
    posts = []
    pdir = root / "posts"
    if not pdir.exists():
        return posts
    for day in sorted(pdir.iterdir()):
        if not day.is_dir():
            continue
        for f in sorted(day.glob("*.md")):
            fm, body = split_post(f.read_text(encoding="utf-8"))
            stem = f.stem
            ptype, _, ver = stem.partition(".")
            if ptype not in config.POST_TYPES:
                continue
            brief_path = root / fm.get("files", {}).get("brief", f"data/{day.name}/{stem}.brief.json")
            brief = json.loads(brief_path.read_text()) if brief_path.exists() else None
            posts.append(Post(day.name, ptype, int(ver or 1), stem, fm, body, brief, f"posts/{day.name}/{stem}.html"))
    return posts


def latest_by_slot(posts: list[Post]) -> dict[tuple[str, str], Post]:
    out: dict[tuple[str, str], Post] = {}
    versions = defaultdict(list)
    for p in posts:
        versions[(p.date, p.post_type)].append(p.version)
        k = (p.date, p.post_type)
        if k not in out or p.version > out[k].version:
            out[k] = p
    for k, p in out.items():
        p.versions = sorted(versions[k])
    return out


def body_html(p: Post) -> str:
    md_text = p.body_md
    if p.fm.get("narrative") == "claude":
        md_text = md_text.replace("<", "&lt;")  # model output is never trusted as HTML
    return markdown.markdown(md_text, extensions=MD_EXT)


def brief_tables(brief: dict | None) -> list[dict]:
    if not brief:
        return []
    out = []
    for sec, title in SECTION_TITLES.items():
        rows = [(k, fmt(v)) for k, v in (brief.get(sec) or {}).items()]
        out.append({"title": title, "rows": rows})
    cal = brief.get("calendar") or {}
    ev = [(f"{e.get('time_et') or 'n/a'} ET", f"{e['name']} [{e['premium_relevance']}]") for e in cal.get("events_today", [])]
    ev += [("days_to_next_fomc", fmt(cal.get("days_to_next_fomc"))), ("next_fomc_date", fmt(cal.get("next_fomc_date")))]
    out.append({"title": "Calendar today", "rows": ev})
    nxt = [(f"{e.get('time_et') or 'n/a'} ET", f"{e['name']} [{e['premium_relevance']}]") for e in cal.get("events_next_session", [])]
    out.append({"title": f"Next session ({cal.get('next_session_date')})", "rows": nxt or [("—", "none listed")]})
    heads = [(h.get("source", ""), h.get("title", "")) for h in cal.get("headlines", [])]
    if heads:
        out.append({"title": "Headlines (titles only)", "rows": heads})
    reg = brief.get("regime") or {}
    out.append({"title": "Regime rules fired", "rows": [("rule", r) for r in reg.get("rules_fired", [])] +
                [("score " + k, f"{v:.2f}") for k, v in (reg.get("scores") or {}).items()]})
    return out


def regime_rules_table() -> list[dict]:
    rules = yaml.safe_load(config.REGIME_RULES_PATH.read_text())
    out = []
    for label, spec in rules["labels"].items():
        out.append({
            "label": label, "icon": LABEL_ICON[label],
            "required": spec.get("required", []),
            "min_evaluable_weight": spec.get("min_evaluable_weight"),
            "conditions": [(n, c["weight"], c["rule"]) for n, c in spec["conditions"].items()],
            "params": spec.get("params", {}),
        })
    return out


def build_site(root: Path, out: Path) -> int:
    env = Environment(loader=FileSystemLoader(config.TEMPLATES_DIR), autoescape=select_autoescape(["html", "xml"]))
    env.globals.update(site_title=config.SITE_TITLE, icons=LABEL_ICON)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(config.STATIC_DIR, out / "static")
    (out / ".nojekyll").write_text("")

    posts = load_posts(root)
    latest = latest_by_slot(posts)
    built_at = datetime.now(config.PT)

    def render(tpl: str, dest: str, **ctx):
        depth = dest.count("/")
        html = env.get_template(tpl).render(rel="../" * depth, built_at=built_at.strftime("%Y-%m-%d %H:%M PT"), **ctx)
        path = out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    # Post pages (every version).
    for p in posts:
        slot = latest[(p.date, p.post_type)]
        render("post.html", p.url, p=p, body=body_html(p), tables=brief_tables(p.brief),
               dq=(p.brief or {}).get("data_quality", {}), versions=slot.versions, is_latest=(slot is p),
               latest_url=slot.url, files=p.fm.get("files", {}))

    # Index: today's three slots (today PT if it is a session, else the latest day with posts).
    today = built_at.date()
    dates = sorted({p.date for p in posts})
    show = today if schedule.is_trading_day(today) or not dates else date.fromisoformat(dates[-1])
    slots = []
    for ptype in reversed(config.POST_TYPES):  # newest first
        p = latest.get((show.isoformat(), ptype))
        sched = schedule.scheduled_time_pt(ptype, show).strftime("%H:%M") if schedule.posts_on(ptype, show) else None
        note = "No post on early-close days" if schedule.is_trading_day(show) and not schedule.posts_on(ptype, show) else None
        slots.append({"post_type": ptype, "post": p, "scheduled": sched, "note": note})
    render("index.html", "index.html", day=show.isoformat(), slots=slots, is_session=schedule.is_trading_day(show),
           early_close=bool(schedule.session(show) and schedule.session(show).early_close))

    # Archive by month.
    months: dict[str, list] = defaultdict(list)
    for d in sorted(dates, reverse=True):
        months[d[:7]].append({"date": d, "posts": [latest[(d, t)] for t in config.POST_TYPES if (d, t) in latest]})
    render("archive.html", "archive/index.html", months=sorted(months.items(), reverse=True))

    # Data page + JSON copies.
    days = []
    data_dir = root / "data"
    if data_dir.exists():
        for d in sorted((x for x in data_dir.iterdir() if x.is_dir()), reverse=True):
            files = sorted(f.name for f in d.glob("*.json"))
            shutil.copytree(d, out / "data" / d.name)
            days.append({"date": d.name, "files": files})
    render("data.html", "data/index.html", days=days, today=show.isoformat())

    # About.
    schema_md = (config.DOCS_DIR / "brief-schema.md").read_text() if (config.DOCS_DIR / "brief-schema.md").exists() else ""
    render("about.html", "about/index.html", rules=regime_rules_table(),
           schema_html=markdown.markdown(schema_md, extensions=MD_EXT),
           relevance=yaml.safe_load(config.REGIME_RULES_PATH.read_text()).get("premium_relevance", {}))

    # Generate page (buttons that dispatch the post workflows).
    render("run.html", "run/index.html", repo=config.GITHUB_REPO, post_types=config.POST_TYPES)

    # RSS + latest.json.
    ordered = sorted(latest.values(), key=lambda p: p.fm.get("generated_at") or "", reverse=True)
    base = config.SITE_BASE_URL.rstrip("/")
    items = []
    for p in ordered[:60]:
        try:
            pub = format_datetime(datetime.fromisoformat(p.fm["generated_at"]))
        except (KeyError, TypeError, ValueError):
            pub = ""
        items.append({"title": f"{p.date} {p.post_type} — {p.icon} {p.label} ({p.fm.get('confidence')})",
                      "link": f"{base}/{p.url}" if base else p.url, "pub": pub,
                      "summary": escape(p.body_md.strip().split("\n\n")[1][:400] if "\n\n" in p.body_md.strip() else p.label)})
    (out / "feed.xml").write_text(env.get_template("feed.xml").render(items=items, base=base or "."), encoding="utf-8")

    api = {"schema_version": config.SCHEMA_VERSION, "built_at": built_at.isoformat(timespec="seconds"), "posts": {}}
    for ptype in config.POST_TYPES:
        cand = [p for p in ordered if p.post_type == ptype]
        if cand:
            p = cand[0]
            api["posts"][ptype] = {
                "date": p.date, "version": p.version, "regime": p.label, "confidence": p.fm.get("confidence"),
                "generated_at": p.fm.get("generated_at"), "url": p.url,
                "brief_url": f"data/{p.date}/{p.stem}.brief.json", "brief": p.brief,
            }
    (out / "api").mkdir(exist_ok=True)
    (out / "api" / "latest.json").write_text(json.dumps(api, indent=1), encoding="utf-8")
    return len(posts)
