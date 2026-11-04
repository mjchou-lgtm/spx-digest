import json
from pathlib import Path

import pytest

from digest import narrative, render
from digest.brief import Brief

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("post_type", ["premarket", "midsession", "afternoon"])
def test_system_prompt_contains_forbidden_content_rules(post_type):
    p = narrative.system_prompt(post_type).lower()
    assert "experienced spx 0dte options trader" in p
    for rule in ["do not comment on risk", "position sizing", "no disclaimers", "not financial advice",
                 "do not make trade calls", "entries, exits", "use only numbers that appear in the brief",
                 "no rounding", "regime label and confidence exactly as given", "no hype",
                 "no headers other than the template"]:
        assert rule in p, rule


def test_template_sections_by_post_type():
    assert "## Since the last post" not in narrative.template_for("premarket")
    assert "## Since the last post" in narrative.template_for("midsession")
    a = narrative.template_for("afternoon")
    assert "## Since the last post" in a and "## Into the close" in a


def _good_text(b: Brief) -> str:
    lv = b.levels
    return f"""## Since the last post
- The open resolved higher.

## Regime: {b.regime.label} ({b.regime.confidence})
Spot at {lv.spot} holds above the opening range high of {b.intraday.or_high}.

## What matters today
- VIX at {b.vol.vix}, term structure {b.vol.term_structure_label}.

## Levels to watch
- {lv.prior_high}: prior-day high.

## What would change the read
- A return inside the opening range.
"""


def test_validate_accepts_template_and_brief_numbers(brief_mid):
    errors, warnings = narrative.validate(_good_text(brief_mid), brief_mid)
    assert errors == [] and warnings == []


def test_validate_rejects_wrong_label_forbidden_phrase_and_missing_section(brief_mid):
    text = _good_text(brief_mid).replace(f"## Regime: {brief_mid.regime.label}", "## Regime: RANGE")
    text = text.replace("## Levels to watch", "## Levels") + "\nThis is risky, so size small. Not financial advice.\n"
    errors, _ = narrative.validate(text, brief_mid)
    joined = " ".join(errors)
    assert "regime header" in joined and "forbidden" in joined and "Levels to watch" in joined


def test_validate_flags_invented_numbers(brief_mid):
    text = _good_text(brief_mid) + "\n- A move to 7777.77 would matter.\n"
    _, warnings = narrative.validate(text, brief_mid)
    assert warnings and "7777.77" in warnings[0]


def test_generate_without_key_fails_cleanly(brief_mid, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = narrative.generate(brief_mid, None, None)
    assert not res.ok and "ANTHROPIC_API_KEY" in res.error
    assert res.request["model"].startswith("claude-")
    assert "temperature" not in res.request  # rejected by current models; low effort instead


def _rendered_posts(brief):
    fm = render.frontmatter(brief, "dry-run", {}, None)
    yield render.post_markdown(fm, render.bullets_body(brief))
    yield render.post_markdown(fm, render.table_body(brief, "forbidden phrases: ['risky']"))
    yield render.post_markdown(fm, _good_text(brief))


def _assert_clean(text: str):
    hits = narrative.find_forbidden(text)
    assert not hits, f"forbidden phrases in rendered post: {hits}"


def test_rendered_posts_contain_no_forbidden_phrases(brief_mid, brief_pre):
    for b in (brief_mid, brief_pre):
        for text in _rendered_posts(b):
            _assert_clean(text)


def test_committed_posts_contain_no_forbidden_phrases():
    for p in (ROOT / "posts").rglob("*.md"):
        _assert_clean(p.read_text())


def test_forbidden_list_covers_spec_examples():
    phrases = narrative.load_forbidden()
    for p in ["risky", "disclaimer", "position size", "not financial advice", "buy the", "sell the"]:
        assert p in phrases
