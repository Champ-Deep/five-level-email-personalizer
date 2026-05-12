from __future__ import annotations

import json
import pytest

from app.levels.schemas import PersonalizeRequest, ProspectInput, SenderInput
from app.services.brand_service import load_brand
from app.services.personalizer import _validate, personalize
from app.levels.schemas import EmailDraft


class MockProvider:
    """Returns deterministic JSON for predictable validation tests."""

    name = "mock"

    def __init__(self, research_payload: dict, email_payload: dict):
        self._research = research_payload
        self._email = email_payload

    async def chat_with_search(self, *args, **kwargs):
        return json.dumps(self._research)

    async def chat(self, *args, **kwargs):
        return json.dumps(self._email)


def test_validate_flags_short_body():
    draft = EmailDraft(
        subject="Quick thought",
        body="Just two words.",
        word_count=3,
        anchor_signal="x",
    )
    warnings = _validate(draft)
    assert any("min 65" in w for w in warnings)


def test_validate_flags_long_subject_and_question():
    draft = EmailDraft(
        subject="This is a really long subject line that goes on?",
        body=" ".join(["word"] * 80),
        word_count=80,
        anchor_signal="x",
    )
    warnings = _validate(draft)
    assert any("max 8" in w for w in warnings)
    assert any("question mark" in w for w in warnings)


def test_validate_flags_banned_words():
    draft = EmailDraft(
        subject="Notes",
        body="We leverage synergy to streamline outcomes. " + " ".join(["word"] * 70),
        word_count=80,
        anchor_signal="x",
    )
    warnings = _validate(draft)
    text = " ".join(warnings).lower()
    assert "leverage" in text or "synergy" in text or "streamline" in text


@pytest.mark.asyncio
async def test_personalize_runs_variations_in_parallel():
    research = {
        "name": "Priya Sharma",
        "title": "VP Sales",
        "company": "Stripe",
        "industry": "Payments",
        "company_signals": ["Acquired Acme last week", "Hiring 5 enterprise AEs"],
        "individual_signals": ["Just posted about RevOps tooling"],
        "industry_trends": ["Payment processors consolidating"],
        "role_pain_points": ["Pipeline coverage shrinking", "Long enterprise cycles"],
        "strongest_trigger": "Recent Acme acquisition",
        "likely_pain_point": "Integrating new GTM motion after acquisition",
    }
    body_text = (
        "Priya — saw the Acme acquisition land last week and the enterprise hiring push. "
        "Most VPs in your seat are juggling two motions at once when an acquisition closes: "
        "keeping the existing pipeline healthy while ramping new AEs against an unfamiliar ICP. "
        "We've helped teams in similar spots cut the ramp gap in half. "
        "Worth a quick look?"
    )
    email = {
        "subject": "Acme acquisition pipeline gap",
        "body": body_text,
        "word_count": 75,
        "anchor_signal": "Recent Acme acquisition",
    }

    from app.levels.schemas import VariationSpec

    brand = load_brand("lakeb2b")
    provider = MockProvider(research, email)
    request = PersonalizeRequest(
        prospect=ProspectInput(name="Priya Sharma", title="VP Sales", domain="stripe.com"),
        sender=SenderInput(name="Subhakar", company="LakeB2B", offer="B2B data intelligence"),
        levels=[5],
        variations=[
            VariationSpec(slot="A", model="anthropic/claude-sonnet-4.6", label="Sonnet 4.6"),
            VariationSpec(slot="B", model="deepseek/deepseek-v4-pro", label="DeepSeek V4"),
            VariationSpec(slot="C", model="openai/gpt-4o", label="GPT-4o"),
        ],
    )
    response = await personalize(request, brand, provider)
    assert response.brand == "lakeb2b"
    assert len(response.variations) == 3
    assert {v.slot for v in response.variations} == {"A", "B", "C"}
    for v in response.variations:
        assert v.email.subject
        assert v.email.body
        assert v.model
    # Back-compat: `emails[5]` populated with slot A.
    assert 5 in response.emails
