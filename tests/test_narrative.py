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
                 "no disclaimers", "not financial advice", "both zones", "no hype", "no headers", "at most 150 words",
                 "verdict: <one line"]:
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
    errors, _ = narrative.validate(_good(brief_mid) + " word" * 200, brief_mid)
    assert any("words" in e for e in errors)
    _, warnings = narrative.validate(_good(brief_mid) + " word" * 150, brief_mid)
    assert any("words" in w for w in warnings)
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

FIELDS = {
    "premarket": ["**VERDICT:**", "**EVENTS**", "**OVERNIGHT:**", "**VOL:**", "**EXPECTED MOVE:**", "**LEVEL STACK**", "**PLAN**"],
    "midsession": ["**VERDICT:**", "**REGIME EVIDENCE**", "**IV CRUSH:**", "**LEVELS IN PLAY**", "**EARLY PLAYBOOK:**"],
    "afternoon": ["**VERDICT:**", "**RANGE SO FAR:**", "**LATE TRIGGER:**", "**THETA NOW:**", "**DO NOT:**"],
}
ET_WITHOUT_PT = re.compile(r"\d{2}:\d{2} ET(?! / \d{2}:\d{2}(?:–\d{2}:\d{2})? PT)")


@pytest.fixture(scope="module")
def cards(brief_pre, brief_mid, brief_td_mid, brief_td_aft):
    return [(b, render.card(b)) for b in (brief_pre, brief_mid, brief_td_mid, brief_td_aft)]


def test_card_has_the_fields_for_its_post_type_in_order(cards):
    for b, text in cards:
        pos = [text.index(f) for f in FIELDS[b.meta.post_type]]
        assert pos == sorted(pos) and pos[0] == 0, b.meta.post_type


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


def test_every_field_line_with_numbers_carries_a_source_link(cards):
    for b, text in cards:
        body = text[: text.index("**Manual inputs open**") if "**Manual inputs open**" in text else text.index("*Missed day?")]
        for block in body.split("\n\n"):
            if block.startswith(("**VERDICT", "**PLAN", "**EARLY PLAYBOOK", "**LATE PLAYBOOK", "**LATE TRIGGER", "**DO NOT", "- ", "★", "—")):
                continue  # rule text, or list blocks whose links sit on the closing line
            if re.search(r"\d", block) and block.startswith("**"):
                assert "](http" in block or "](../../concepts/" in block, block[:80]
        for head in ("**LEVEL STACK**", "**REGIME EVIDENCE**", "**LEVELS IN PLAY**"):
            if head in body:
                seg = body[body.index(head):].split("\n\n**")[0]
                assert "](http" in seg, head


def test_all_times_show_et_and_pt(cards):
    for b, text in cards:
        assert not ET_WITHOUT_PT.findall(text), ET_WITHOUT_PT.findall(text)


def test_card_narrative_and_verdict_from_claude_are_placed(brief_mid):
    text = render.card(brief_mid, "regime classified as balance; playbook: none, sit out", "Two-way trade around VWAP.")
    assert text.startswith("**VERDICT:** regime classified as balance; playbook: none, sit out\n")
    assert text.index("Two-way trade around VWAP.") < text.index("*Missed day?")
    assert render.unavailable_body(brief_mid).startswith("**Narrative unavailable")


def test_default_verdicts(brief_pre, brief_mid, brief_td_mid, brief_td_aft):
    assert render.default_verdict(brief_pre).startswith("no trade until the 10:30 ET / 07:30 PT classification; lean:")
    assert render.default_verdict(brief_mid) == "regime classified as balance; playbook: none"
    assert render.default_verdict(brief_td_mid) == "regime classified as trend_down; playbook: early"
    assert render.default_verdict(brief_td_aft) == "regime confirmed: trend_down; late playbook live"
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
