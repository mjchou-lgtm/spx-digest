#!/usr/bin/env python3
"""Create the cron-job.org jobs that trigger this repo's workflows at the slot times.

GitHub's own scheduler starts this repo's cron runs hours late (see README, "Workflows"), so an
outside clock sends the same "Run workflow" request GitHub's UI sends. Run this once from your
own terminal; it talks only to api.cron-job.org and needs two values you keep to yourself:

    read -s CRONJOB_API_KEY && export CRONJOB_API_KEY    # cron-job.org Console -> Settings -> API
    read -s GITHUB_TOKEN && export GITHUB_TOKEN          # fine-grained token: this repo only, Actions: read and write
    python3 scripts/cronjob_setup.py                     # add --list to only show existing jobs

Jobs are matched by title, so running it again updates the existing ones instead of adding
duplicates. Each job keeps the workflow's own checks (the time window, trading days, early
closes, one post per slot), so a job that fires on a holiday just makes the workflow skip.
Standard library only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.cron-job.org"
REPO = os.environ.get("DIGEST_REPO", "mjchou-lgtm/spx-digest")
TZ = "America/Los_Angeles"
WEEKDAYS = [1, 2, 3, 4, 5]

# (title, workflow file, inputs, hour PT, minute PT)
JOBS = [
    ("spx-digest premarket 06:15 PT", "premarket.yml", {"force": "false"}, 6, 15),
    ("spx-digest straddle 06:35 PT (09:35 ET print)", "straddle.yml", {"scheduled": "true"}, 6, 35),
    ("spx-digest midsession 07:45 PT", "midsession.yml", {"force": "false"}, 7, 45),
    ("spx-digest afternoon 11:15 PT", "afternoon.yml", {"force": "false"}, 11, 15),
    ("spx-digest afternoon 09:00 PT (early-close days only)", "afternoon.yml", {"force": "false"}, 9, 0),
]


def call(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        sys.exit(f"cron-job.org {method} {path} failed: HTTP {e.code} {detail}")


def job_spec(title: str, workflow: str, inputs: dict, hour: int, minute: int, token: str) -> dict:
    return {
        "title": title,
        "url": f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches",
        "enabled": True,
        "saveResponses": True,
        "requestMethod": 1,  # POST
        "schedule": {"timezone": TZ, "expiresAt": 0, "hours": [hour], "minutes": [minute],
                     "mdays": [-1], "months": [-1], "wdays": WEEKDAYS},
        "extendedData": {
            "headers": {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            "body": json.dumps({"ref": "main", "inputs": inputs}),
        },
    }


def main() -> None:
    key = os.environ.get("CRONJOB_API_KEY") or sys.exit("set CRONJOB_API_KEY (cron-job.org Console -> Settings -> API)")
    existing = {j.get("title"): j for j in call("GET", "/jobs", key).get("jobs", [])}
    if "--list" in sys.argv:
        for j in existing.values():
            print(f"{j.get('jobId')}: {j.get('title')!r} enabled={j.get('enabled')} next={j.get('nextExecution')}")
        return
    token = os.environ.get("GITHUB_TOKEN") or sys.exit("set GITHUB_TOKEN (fine-grained token, this repo only, Actions: read and write)")
    for title, workflow, inputs, hour, minute in JOBS:
        spec = job_spec(title, workflow, inputs, hour, minute, token)
        if title in existing:
            jid = existing[title]["jobId"]
            call("PATCH", f"/jobs/{jid}", key, {"job": spec})
            print(f"updated  {jid}: {title}")
        else:
            jid = call("PUT", "/jobs", key, {"job": spec}).get("jobId")
            print(f"created  {jid}: {title}")
        time.sleep(1.1)  # create/update limits: 1 request per second
    print(f"\nDone. Jobs fire Monday-Friday in {TZ}; check the Console for the next run time.\n"
          f"GitHub answers 204 to a dispatch, which cron-job.org shows as a success.")


if __name__ == "__main__":
    main()
