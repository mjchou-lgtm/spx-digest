import re
from pathlib import Path

import pytest

from digest import narrative, render
from digest.brief import Brief

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("post_type", ["premarket", "midsession", "afternoon"])
def test_system_prompt_rules(post_type):
    p = narrative.system_prompt(post_type).lower()
    for rule in ["reference only fields in the json", "use only numbers that appear in it", "no rounding",
                 "do not substitute your own label", "do not invent triggers, strikes, entries, exits, sizes, stops or targets",
                 "do not say premium is expensive", "likely to be exceeded given the regime", "debit spread", "sit out",
                 "no disclaimers", "not financial advice", "both zones", "no hype", "no headers", "at most 80 words", "do not recite them",
                 "learning tool", "plain english", "do not assume they know the jargon", "say why a thing matters",
                 "verdict: <one short line in plain english"]:
        assert rule in p, rule


def test_user_message_carries_fields_and_required_phrases(brief_mid):
    m = narrative.user_message(brief_mid, "2026-11-06 premarket: no trade until the 10:30 ET / 07:30 PT classification")
    assert "<fields>" in m and '"regime"' in m and '"playbook"' in m and "<previous_verdict>" in m
    assert '"balance"' in m and '"playbook: none"' in m
    assert '"sources"' not in m  # fetch bookkeeping is not sent


def _good(b: Brief) -> str:
    v = render.default_verdict(b)
    return f"VERDICT: {v}\n\nVIX1D is {b.vol.vix1d} and the developing POC is {b.intraday.dev_poc}. Spot is {b.levels.spot}."


def test_validate_accepts_default_verdict_and_field_numbers(brief_mid, brief_td_aft, brief_pre):
    for b in (brief_mid, brief_td_aft):
        errors, warnings = narrative.validate(_good(b), b)
        assert errors == [] and warnings == [], (errors, warnings)
    text = f"VERDICT: {render.default_verdict(brief_pre)}\n\nThe classification is at 10:30 ET / 07:30 PT."
    assert narrative.validate(text, brief_pre) == ([], [])


def test_validate_rejects_wrong_label_or_playbook(brief_mid):
    wrong = _good(brief_mid).replace("balance", "trend_up")
    errors, _ = narrative.validate(wrong, brief_mid)
    assert any("verdict must contain 'balance'" in e for e in errors)
    wrong = _good(brief_mid).replace("playbook: none", "playbook: early")
    assert any("playbook: none" in e for e in narrative.validate(wrong, brief_mid)[0])


def test_validate_rejects_missing_verdict_headers_length_and_forbidden(brief_mid):
    assert "VERDICT" in narrative.validate("Balance day.", brief_mid)[0][0]
    errors, _ = narrative.validate(_good(brief_mid) + "\n\n## Levels\nmore", brief_mid)
    assert any("headers" in e for e in errors)
    errors, _ = narrative.validate(_good(brief_mid) + " word" * 120, brief_mid)
    assert any("words" in e for e in errors)
    errors, warnings = narrative.validate(_good(brief_mid) + " word" * 80, brief_mid)
    assert not errors and any("words" in w for w in warnings)
    errors, _ = narrative.validate(_good(brief_mid) + " This is risky. Not financial advice.", brief_mid)
    assert any("forbidden" in e for e in errors)


def test_validate_flags_invented_numbers(brief_mid):
    _, warnings = narrative.validate(_good(brief_mid) + " A move to 7777.77 would matter.", brief_mid)
    assert warnings and "7777.77" in warnings[0]


def test_split_output():
    v, body = narrative.split_output("VERDICT: regime classified as balance; playbook: none\n\nTwo-way trade.")
    assert v == "regime classified as balance; playbook: none" and body == "Two-way trade."
    assert narrative.split_output("no verdict here")[0] is None


def test_generate_without_key_fails_cleanly(brief_mid, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = narrative.generate(brief_mid)
    assert not res.ok and "ANTHROPIC_API_KEY" in res.error
    assert res.request["model"].startswith("claude-")
    assert "temperature" not in res.request  # rejected by current models; low effort instead


# --- the card ---------------------------------------------------------------------------------

SECTIONS = ["## Verdict", "## Technical", "## News / macro", "*Missed day?", "**Sources**"]
TECHNICAL = {
    "premarket": ["**Overnight:**", "**Volatility:**", "**What options are pricing:**", "**Key levels**", "**Your playbooks: decided at 10:30 ET"],
    "midsession": ["**What kind of day: ", "**Where price is now:**", "**Option prices:**", "**Key levels**", "**Your playbooks: "],
    "afternoon": ["**What kind of day: ", "**Where price is now:**", "**Option prices:**", "**Key levels**", "**Your playbooks: "],
}
ET_WITHOUT_PT = re.compile(r"\d{2}:\d{2} ET(?! / \d{2}:\d{2}(?:–\d{2}:\d{2})? PT)")


def section(text: str, name: str) -> str:
    start = text.index(name)
    nxt = [text.index(s, start + 1) for s in SECTIONS if s in text[start + 1:]]
    return text[start: min(nxt) if nxt else len(text)]


@pytest.fixture(scope="module")
def cards(brief_pre, brief_mid, brief_td_mid, brief_td_aft):
    return [(b, render.card(b)) for b in (brief_pre, brief_mid, brief_td_mid, brief_td_aft)]


def test_card_sections_in_order_with_verdict_first(cards):
    for b, text in cards:
        pos = [text.index(s) for s in SECTIONS]
        assert pos == sorted(pos) and pos[0] == 0, b.meta.post_type
        assert text.startswith(f"## Verdict\n\n**{render.default_verdict(b)}**\n\n*")
        assert "\n\nWhat to watch:\n\n- " in section(text, "## Verdict")
        tech = section(text, "## Technical")
        tpos = [tech.index(f) for f in TECHNICAL[b.meta.post_type]]
        assert tpos == sorted(tpos), b.meta.post_type


def test_verdict_summary_lists_levels_indicators_and_triggers(brief_pre, brief_mid, brief_td_mid, brief_td_aft):
    pre = render.watch(brief_pre)
    assert pre[0].startswith("The open: futures point to ") and any(w.startswith("Ceiling: ") for w in pre) and any(w.startswith("Floor: ") for w in pre)
    assert any(w.startswith("Expected move: options are pricing about ±") for w in pre)
    assert any(w.startswith("Option prices: the 1-day volatility gauge (VIX1D) is ") for w in pre)
    assert any(w.startswith("Scheduled news that can move the market: 08:30 ET / 05:30 PT Monthly jobs report") for w in pre)
    assert any(w.startswith("What decides the day type: ") for w in pre)
    mid = render.watch(brief_mid)
    assert mid[0] == "Early setup: not live, option prices are high on a range-bound day (the sit-out combination)."
    assert any("since the open" in w and "IV crush" in w and "VIX1D" in w for w in mid) and any(w.startswith("What would change this read: ") for w in mid)
    td = render.watch(brief_td_mid)
    assert td[0].startswith("Early setup is live. Trigger: two 5-minute closes in a row below the bottom of the first 30 minutes (")
    assert "It is off on a 5-minute close back above today's average price (VWAP" in td[0]
    assert "Out by 13:00 ET / 10:00 PT either way" in td[0] and "debit spread (buy one option and sell a further-out one" in td[0]
    aft = render.watch(brief_td_aft)
    assert aft[0].startswith("Late setup (14:30–15:45 ET / 11:30–12:45 PT): ready, opens 14:30 ET / 11:30 PT. Trigger: ")
    assert any("time value is left" in w and "Be flat by 15:45 ET / 12:45 PT" in w for w in aft)
    assert any(w.startswith("The downtrend day read is still holding: price (") for w in aft)
    for w in pre + mid + td + aft:
        assert "](" not in w and len(w) < 420  # plain text, readable on the home page
    fm = render.frontmatter(brief_mid, "dry-run", {}, None)
    assert fm["watch"] == mid and fm["meaning"].startswith("In plain terms: buyers and sellers roughly agree on price")


def test_cards_explain_terms_instead_of_assuming_them(cards):
    """Jargon is either replaced or glossed where it appears, and the glossary is linked from every card."""
    for b, text in cards:
        body = text[: text.index("**Sources**")]
        for raw in ("prior VAH", "prior VAL", "prior POC", "dev VAH", "dev VAL", "dev POC", "OR high", "OR low", "O/N ", "spot_", "pctile",
                    "extrinsic", "D-profile", "contango", "backwardation"):
            assert raw not in body, (b.meta.post_type, raw)
        if "VWAP" in body:
            assert "today's average price (VWAP" in body or "average price (VWAP)" in body
        if "IV crush" in body:
            assert "deflat" in body  # explained as option prices deflating after the open
        if "straddle" in section(text, "## Technical"):
            assert "a call plus a put at the current price" in text or "straddle print" in text or "straddle quote" in text
        assert "value area is the zone that held about 70% of a day's trading" in text.lower() or b.meta.market_closed_mode
        assert "concepts/glossary.html" in text
    pre, mid = cards[0][1], cards[1][1]
    assert "*How to read this: the first hour sets the tone." in pre
    assert "*In plain terms: buyers and sellers roughly agree on price" in mid


def test_verdict_section_stays_short(cards):
    for b, text in cards:
        v = section(text, "## Verdict")
        assert v.count("\n- ") <= 7 and len(v.split()) <= 330, (b.meta.post_type, len(v.split()))


def test_levels_merge_confluence_into_one_line(brief_mid, brief_pre):
    cs = render.clusters(brief_mid)
    tol = render._tol()
    assert sum(len(c["names"]) for c in cs) == len(brief_mid.levels.level_stack)
    for a, b_ in zip(cs, cs[1:]):
        assert a["lo"] - b_["hi"] > tol  # separate lines are further apart than the tolerance
    lines = render._level_lines(brief_mid, 3)
    assert sum(1 for l in lines if "▶ price now" in l) == 1 and len(lines) <= 7
    assert any("★" in l for l in render._level_lines(brief_pre, None))


def test_news_macro_section(cards, brief_pre, brief_mid):
    for b, text in cards:
        news = section(text, "## News / macro")
        assert "](http" in news
        assert "What kind of day" not in news and "VWAP" not in news  # technical content stays out
    pre = section(render.card(brief_pre), "## News / macro")
    assert "08:30 ET / 05:30 PT: Monthly jobs report (Employment Situation) (high impact)" in pre and "Big-tech earnings last night" in pre
    assert "Fed speaker: " in pre
    from digest.brief import Event
    ev = Event(date="2026-11-06", time_et="10:00", name="Prelim UoM Consumer Sentiment", category="FF_MEDIUM", premium_relevance="medium")
    assert render._event_name(ev) == "Preliminary University of Michigan Consumer Sentiment"
    assert "already out" in section(render.card(brief_mid), "## News / macro") and "already out" not in pre
    assert pre.count("- Headline: ") <= 3 and "termination of enforcement action" not in pre  # routine Fed notices are dropped


def test_only_big_moves_in_other_markets_are_shown(brief_mid):
    quiet = brief_mid.model_copy(deep=True)
    quiet.cross_asset.us10y_change_bp, quiet.cross_asset.dxy_change_pct = 1.0, 0.1
    quiet.cross_asset.oil_change_pct, quiet.cross_asset.gold_change_pct = 0.3, 0.2
    assert render._other_markets(quiet) is None
    quiet.cross_asset.us10y_change_bp = -8.0
    line = render._other_markets(quiet)
    assert "10-year Treasury yield is down 8 basis points" in line and "oil" not in line and "spill into stocks" in line


def test_card_ends_with_missed_day_and_sources(cards):
    for b, text in cards:
        assert "*Missed day? A no-trade day is a valid outcome. Tomorrow's bar is the normal bar.*" in text
        tail = text[text.index("**Sources**"):]
        assert tail.count("](http") >= 8 and "fetched" in tail
        for s in b.data_quality.sources:
            assert s.url in tail
        assert "Dealer gamma / GEX: not computed or estimated (vendor link not set)" in tail
        for slug in ("daily-structure", "premium", "volume-profile", "edge", "rules"):
            assert f"concepts/{slug}.html" in tail


def test_technical_lines_with_numbers_carry_a_source_link(cards):
    for b, text in cards:
        for block in section(text, "## Technical").split("\n\n"):
            if block.startswith("**") and not block.startswith("**Your playbooks") and re.search(r"\d", block):
                assert "](http" in block.split("\n")[0], block[:80]


def test_all_times_show_et_and_pt(cards):
    for b, text in cards:
        assert not ET_WITHOUT_PT.findall(text), ET_WITHOUT_PT.findall(text)
        assert not any(ET_WITHOUT_PT.findall(w) for w in render.watch(b))


def test_card_narrative_and_verdict_from_claude_are_placed(brief_mid):
    text = render.card(brief_mid, "regime classified as balance; playbook: none, sit out", "Two-way trade around VWAP.")
    assert text.startswith("## Verdict\n\n**regime classified as balance; playbook: none, sit out**\n")
    assert text.index("Two-way trade around VWAP.") < text.index("## Technical")
    un = render.unavailable_body(brief_mid)
    assert un.index("Narrative unavailable") < un.index("## Technical") and f"**{render.default_verdict(brief_mid)}**" in un


def test_default_verdicts(brief_pre, brief_mid, brief_td_mid, brief_td_aft):
    assert render.default_verdict(brief_pre).startswith("No trade until the day type is set at 10:30 ET / 07:30 PT. Early lean: ")
    assert render.default_verdict(brief_mid) == "Range-bound day (balance); playbook: none"
    assert render.default_verdict(brief_td_mid) == "Downtrend day (trend_down); playbook: early"
    assert render.default_verdict(brief_td_aft) == "Downtrend day confirmed (trend_down); late playbook live"
    for b in (brief_pre, brief_mid, brief_td_mid, brief_td_aft):
        assert all(req in render.default_verdict(b) for req in render.verdict_requirements(b))


def _assert_clean(text: str):
    hits = narrative.find_forbidden(text)
    assert not hits, f"forbidden phrases in rendered post: {hits}"


def test_rendered_posts_contain_no_forbidden_phrases(cards):
    for b, text in cards:
        _assert_clean(render.post_markdown(render.frontmatter(b, "dry-run", {}, None), text))


def test_committed_posts_contain_no_forbidden_phrases():
    for p in (ROOT / "posts").rglob("*.md"):
        _assert_clean(p.read_text())


def test_forbidden_list_covers_spec_examples():
    phrases = narrative.load_forbidden()
    for p in ["risky", "disclaimer", "position size", "not financial advice", "buy the", "sell the"]:
        assert p in phrases
