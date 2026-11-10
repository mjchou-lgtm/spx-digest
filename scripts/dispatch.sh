#!/usr/bin/env bash
# Start one of the post workflows now, from anywhere that can run curl (a laptop cron,
# a hosted cron service, a shell). The workflow itself still decides whether to post:
# with force=false it applies the same time window and trading-day checks as a cron run.
#
#   GITHUB_TOKEN=github_pat_… scripts/dispatch.sh premarket            # like the cron: only inside the window
#   GITHUB_TOKEN=github_pat_… scripts/dispatch.sh afternoon true       # ignore the window, post now
#   GITHUB_TOKEN=github_pat_… scripts/dispatch.sh straddle             # 09:35 ET straddle print, cron rules (straddle true = capture now)
#
# The token is a fine-grained personal access token limited to this repository with
# Actions: Read and write, nothing else. Never commit it.
set -euo pipefail

post=${1:?usage: dispatch.sh premarket|midsession|afternoon|straddle [force: true|false]}
force=${2:-false}
repo=${DIGEST_REPO:-mjchou-lgtm/spx-digest}
: "${GITHUB_TOKEN:?set GITHUB_TOKEN to a fine-grained token with Actions: read and write on $repo}"

case "$post" in
  premarket|midsession|afternoon) inputs="{\"force\":\"$force\"}" ;;
  straddle) [ "$force" = true ] && inputs="{}" || inputs='{"scheduled":"true"}' ;;
  *) echo "unknown workflow: $post" >&2; exit 2 ;;
esac

curl -sS --fail-with-body -X POST "https://api.github.com/repos/$repo/actions/workflows/$post.yml/dispatches" \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "{\"ref\":\"main\",\"inputs\":$inputs}"
echo "dispatched $post (force=$force) on $repo"
