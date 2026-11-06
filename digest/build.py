"""Static site: index (today's three slots), post pages, archive, /data/, /about, /concepts, feed.xml, api/latest.json."""
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
        return self.fm.get("regime", "undetermined")

    @property
    def icon(self) -> str:
        return LABEL_ICON.get(self.label, "•")

    @property
    def time_et(self) -> str:
        try:
            return datetime.fromisoformat(self.fm["generated_at"]).astimezone(config.ET).strftime("%H:%M")
        except (KeyError, TypeError, ValueError):
            return ""

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
        rows = [(k, fmt(v)) for k, v in (brief.get(sec) or {}).items() if k != "level_stack"]
        if rows:
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
    out.append({"title": "Regime rules", "rows": [("fired", r) for r in reg.get("rules_fired", [])] +
                [("not met", r) for r in reg.get("rules_failed", [])] + [("conflict", r) for r in reg.get("conflicts", [])] +
                [("score " + k, f"{v:.2f}") for k, v in (reg.get("scores") or {}).items()]})
    return out


def rules_tables() -> dict:
    """Thresholds and playbook settings for the About and rules pages (straight from the YAML files)."""
    rules = yaml.safe_load(config.REGIME_RULES_PATH.read_text())
    pb = yaml.safe_load(config.PLAYBOOK_PATH.read_text())

    def show(v):
        if v is None:
            return "not set"
        if isinstance(v, list):
            return ", ".join(map(str, v))
        return "yes" if v is True else "no" if v is False else str(v)

    return {
        "classify": [(k, show(v)) for k, v in rules["classify"].items()],
        "levels": [(k, show(v)) for k, v in rules["levels"].items()],
        "premium": [(k, show(v)) for k, v in rules["premium"].items()],
        "playbook": {sec: [(k, show(v)) for k, v in pb[sec].items()] for sec in ("shared", "early", "late")},
        "relevance": rules.get("premium_relevance", {}),
    }


def theta_rows() -> list[tuple[str, int]]:
    from datetime import time as _t

    from digest.indicators.premium import theta_table

    rules = yaml.safe_load(config.REGIME_RULES_PATH.read_text())
    d = date(2026, 1, 5)  # any normal session: the table depends only on time of day
    o, c = datetime.combine(d, _t(9, 30), tzinfo=config.ET), datetime.combine(d, _t(16, 0), tzinfo=config.ET)
    return theta_table(rules["premium"]["theta_table_et"], o, c)


def concept_pages() -> list[dict]:
    """concepts/*.md -> pages. `{{theta_table}}` and `{{rules_table}}` are filled from the YAML files."""
    from digest.timefmt import both

    out = []
    if not config.CONCEPTS_DIR.exists():
        return out
    rt = rules_tables()
    theta_md = "\n".join(["| Time | ATM extrinsic remaining |", "|---|---|"] + [f"| {both(t)} | {p}% |" for t, p in theta_rows()])
    rows = {k: dict(v) for k, v in rt["playbook"].items()}
    e, l, sh = rows["early"], rows["late"], rows["shared"]
    rules_md = "\n".join([
        "| | Early | Late |", "|---|---|---|",
        f"| Window | {both(e['window_et'].split(', ')[0])} to {both(e['window_et'].split(', ')[1])} | {both(l['window_et'].split(', ')[0])} to {both(l['window_et'].split(', ')[1])} |",
        f"| Precondition | regime is one of {e['regimes']}; IV crush done (straddle at or below {rt['premium'][0][1]}% vs its 09:35 ET print), or high IV | an objective trigger: acceptance outside the developing value area, or a break of a confluence level with volume returning |",
        f"| Instrument | {sh['instrument']}; {e['high_iv_instrument']} when VIX1D is high or extreme | {sh['instrument']} |",
        f"| Sizing | {e['sizing']} | {l['sizing']} |",
        f"| Stop | {e['stop']} | {l['stop']} |",
        f"| Target | {e['target']} | {l['target']} |",
        f"| Time stop | {both(e['time_stop_et'])} | flat by {both(sh['flat_by_et'])} |",
        f"| Max trades | {e['max_trades']} | {l['max_trades']} |",
        f"| Premium cap | n/a | {l['premium_cap']} |",
        f"| Never | {sh['never']} | {sh['never']} |",
    ])
    for f in sorted(config.CONCEPTS_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8").replace("{{theta_table}}", theta_md).replace("{{rules_table}}", rules_md)
        title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), f.stem)
        out.append({"slug": f.stem, "title": title, "html": markdown.markdown(text, extensions=MD_EXT + ["attr_list", "toc"])})
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
        slots.append({"post_type": ptype, "post": p, "scheduled": sched, "note": note,
                      "scheduled_et": schedule.scheduled_time_pt(ptype, show).astimezone(config.ET).strftime("%H:%M") if sched else None})
    render("index.html", "index.html", day=show.isoformat(), slots=slots, is_session=schedule.is_trading_day(show),
           early_close=bool(schedule.session(show) and schedule.session(show).early_close),
           repo=config.GITHUB_REPO, post_types=config.POST_TYPES)

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
    rt = rules_tables()
    render("about.html", "about/index.html", rt=rt, schema_html=markdown.markdown(schema_md, extensions=MD_EXT), relevance=rt["relevance"])

    # Concept explainers (linked from every post).
    concepts = concept_pages()
    for c in concepts:
        render("concept.html", f"concepts/{c['slug']}.html", c=c, concepts=concepts)
    render("concepts.html", "concepts/index.html", concepts=concepts)

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
        items.append({"title": f"{p.date} {p.post_type}: {p.icon} {p.label}" + (f" ({p.fm['confidence']})" if p.fm.get("confidence") else ""),
                      "link": f"{base}/{p.url}" if base else p.url, "pub": pub,
                      "summary": escape(p.fm.get("verdict") or (p.body_md.strip().split("\n\n")[1][:400] if "\n\n" in p.body_md.strip() else p.label))})
    (out / "feed.xml").write_text(env.get_template("feed.xml").render(items=items, base=base or "."), encoding="utf-8")

    api = {"schema_version": config.SCHEMA_VERSION, "built_at": built_at.isoformat(timespec="seconds"), "posts": {}}
    for ptype in config.POST_TYPES:
        cand = [p for p in ordered if p.post_type == ptype]
        if cand:
            p = cand[0]
            api["posts"][ptype] = {
                "date": p.date, "version": p.version, "regime": p.label, "playbook": p.fm.get("playbook"), "verdict": p.fm.get("verdict"),
                "generated_at": p.fm.get("generated_at"), "url": p.url,
                "brief_url": f"data/{p.date}/{p.stem}.brief.json", "brief": p.brief,
            }
    (out / "api").mkdir(exist_ok=True)
    (out / "api" / "latest.json").write_text(json.dumps(api, indent=1), encoding="utf-8")
    return len(posts)
