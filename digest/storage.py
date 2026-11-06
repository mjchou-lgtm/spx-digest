"""Append-only persistence. A day's files are never overwritten: a re-run of the
same post writes a new version (premarket.2.md, premarket.2.brief.json, ...)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from digest import config

KINDS = ("raw", "brief", "llm")


@dataclass(frozen=True)
class PostPaths:
    root: Path
    date: str
    post_type: str
    version: int

    @property
    def stem(self) -> str:
        return self.post_type if self.version == 1 else f"{self.post_type}.{self.version}"

    def data(self, kind: str) -> Path:
        return self.root / "data" / self.date / f"{self.stem}.{kind}.json"

    @property
    def post(self) -> Path:
        return self.root / "posts" / self.date / f"{self.stem}.md"

    def all(self) -> list[Path]:
        return [self.post, *(self.data(k) for k in KINDS)]


def existing_versions(root: Path, date: str, post_type: str) -> list[int]:
    vs = set()
    pat = re.compile(rf"^{re.escape(post_type)}(?:\.(\d+))?\.(md|raw\.json|brief\.json|llm\.json)$")
    for d in (root / "posts" / date, root / "data" / date):
        if d.exists():
            for p in d.iterdir():
                m = pat.match(p.name)
                if m:
                    vs.add(int(m.group(1) or 1))
    return sorted(vs)


def next_paths(root: Path, date: str, post_type: str) -> PostPaths:
    vs = existing_versions(root, date, post_type)
    return PostPaths(root, date, post_type, (max(vs) + 1) if vs else 1)


def latest_paths(root: Path, date: str, post_type: str) -> PostPaths | None:
    vs = [v for v in existing_versions(root, date, post_type) if PostPaths(root, date, post_type, v).post.exists()]
    return PostPaths(root, date, post_type, max(vs)) if vs else None


def write_new(path: Path, text: str) -> None:
    """Exclusive create — raises FileExistsError rather than overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:
        f.write(text)


def write_json_new(path: Path, obj) -> None:
    write_new(path, json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n")


def output_root(write_to_dataset: bool) -> Path:
    return config.ROOT if write_to_dataset else config.ROOT / "out"


# --- 09:35 ET straddle print (auto capture or manual entry; never overwritten) ---------

def straddle_files(root: Path, date: str) -> list[Path]:
    d = root / "data" / date
    return sorted(d.glob("straddle_0935*.json"), key=lambda p: int((re.search(r"\.(\d+)\.json$", p.name) or [0, 1])[1])) if d.exists() else []


def write_straddle(root: Path, date: str, record: dict) -> Path:
    n = len(straddle_files(root, date)) + 1
    path = root / "data" / date / ("straddle_0935.json" if n == 1 else f"straddle_0935.{n}.json")
    write_json_new(path, record)
    return path


def read_straddle(roots: list[Path], date: str) -> dict | None:
    """The day's 09:35 ET print: the latest manual entry if there is one, else the first automatic capture."""
    recs = [json.loads(p.read_text()) for r in roots for p in straddle_files(r, date)]
    manual = [r for r in recs if r.get("source") == "manual"]
    auto = [r for r in recs if r.get("source") != "manual"]
    return manual[-1] if manual else (auto[0] if auto else None)
