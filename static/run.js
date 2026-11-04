// Generate page: dispatch a post workflow via the GitHub API with a token kept in this browser.
// Without a token, the buttons are plain links to the workflow's page on GitHub.
(function () {
  "use strict";
  var root = document.getElementById("gen");
  if (!root) return;
  var REPO = root.dataset.repo;
  var API = "https://api.github.com/repos/" + REPO + "/actions";
  var KEY = "spx-digest:gh-token";
  var statusEl = document.getElementById("gen-status");
  var summary = document.getElementById("gen-token-summary");
  var busy = false;

  function getToken() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch (e) {} refreshSummary(); }
  function refreshSummary() {
    if (!summary) return;
    summary.textContent = getToken() ? "One-click mode: token saved in this browser" : "One-click mode: not set up (buttons open GitHub)";
  }

  function gh(path, opts) {
    opts = opts || {};
    opts.headers = {
      "Accept": "application/vnd.github+json",
      "Authorization": "Bearer " + getToken(),
      "X-GitHub-Api-Version": "2022-11-28",
    };
    if (opts.body) opts.headers["Content-Type"] = "application/json";
    return fetch(API + path, opts);
  }

  function checked(id) { var el = document.getElementById(id); return !!(el && el.checked); }
  function show(html) { statusEl.hidden = false; statusEl.innerHTML = html; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function link(url, text) { return '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + "</a>"; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function errText(res) {
    var msg = res.status + " " + res.statusText;
    try { var j = await res.json(); if (j.message) msg += ": " + j.message; } catch (e) {}
    if (res.status === 401) msg += " (token invalid or expired)";
    if (res.status === 403 || res.status === 404) msg += " (token needs Actions: Read and write on " + REPO + ")";
    return msg;
  }

  async function findRun(post, since) {
    var res = await gh("/workflows/" + post + ".yml/runs?event=workflow_dispatch&per_page=5");
    if (!res.ok) throw new Error(await errText(res));
    var runs = (await res.json()).workflow_runs || [];
    return runs.find(function (r) { return Date.parse(r.created_at) >= since; }) || null;
  }

  async function outcome(run) {
    // The deploy job is skipped when the run decided not to post (outside a session, nothing to discuss).
    var res = await gh("/runs/" + run.id + "/jobs?per_page=20");
    if (!res.ok) return null;
    var jobs = (await res.json()).jobs || [];
    var dep = jobs.find(function (j) { return /deploy/i.test(j.name); });
    return dep ? dep.conclusion : null;
  }

  async function dispatch(post) {
    var dry = checked("opt-dry"), empty = checked("opt-empty");
    var since = Date.now() - 15000;  // tolerate clock skew vs GitHub
    show("Starting <b>" + esc(post) + "</b>…");
    var res = await gh("/workflows/" + post + ".yml/dispatches", {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs: { force: "true", dry_run: String(dry), confirm_empty: String(empty) } }),
    });
    if (!res.ok) throw new Error(await errText(res));

    var run = null, started = Date.now();
    while (Date.now() - started < 15 * 60 * 1000) {
      await sleep(run ? 6000 : 3000);
      run = (await findRun(post, since)) || run;
      if (!run) { show("Queued <b>" + esc(post) + "</b>; waiting for GitHub to start the run…"); continue; }
      var mins = Math.round((Date.now() - started) / 60000);
      if (run.status !== "completed") {
        show("<b>" + esc(post) + "</b>: " + esc(run.status.replace("_", " ")) + (mins ? " (" + mins + " min)" : "") + " · " + link(run.html_url, "watch the run"));
        continue;
      }
      if (run.conclusion !== "success") {
        show("<b>" + esc(post) + "</b> run ended: <b>" + esc(run.conclusion) + "</b> · " + link(run.html_url, "open the log"));
        return;
      }
      if (dry) {
        show("Dry run of <b>" + esc(post) + "</b> finished. Output is attached to the run as an artifact · " + link(run.html_url, "open the run"));
        return;
      }
      var dep = await outcome(run);
      if (dep === "skipped") {
        show("<b>" + esc(post) + "</b> ran but wrote no post (for example: not a trading day and nothing to discuss). The skip reason is in the " + link(run.html_url, "run log") + ".");
        return;
      }
      show("Posted <b>" + esc(post) + "</b> and redeployed · " + link(root.dataset.site + "?t=" + Date.now(), "open the digest") + " · " + link(run.html_url, "run"));
      return;
    }
    show("Still running after 15 minutes · " + link(run ? run.html_url : "https://github.com/" + REPO + "/actions", "check GitHub Actions"));
  }

  root.querySelectorAll("[data-post]").forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      if (!getToken()) return;  // no token: follow the link to GitHub's Run workflow page
      ev.preventDefault();
      if (busy) return;
      busy = true;
      root.classList.add("busy");
      dispatch(btn.dataset.post).catch(function (e) {
        show("Could not start <b>" + esc(btn.dataset.post) + "</b>: " + esc(e.message) + " · " + link(btn.href, "run it on GitHub instead"));
      }).finally(function () { busy = false; root.classList.remove("busy"); });
    });
  });

  var form = document.getElementById("gen-token-form");
  if (form) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var inp = document.getElementById("gen-token-input");
      var t = inp.value.trim();
      if (t) setToken(t);
      inp.value = "";
    });
    document.getElementById("gen-token-forget").addEventListener("click", function () { setToken(""); });
  }
  refreshSummary();
})();
