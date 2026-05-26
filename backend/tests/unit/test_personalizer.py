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


class SequenceMockProvider:
    """Captures every chat() prompt + lets the test assert per-step
    angles. Returns a distinct email payload per call so the
    personalizer sees each step as 'different content'."""

    name = "mock-seq"

    def __init__(self, research_payload: dict):
        self._research = research_payload
        self.calls: list[str] = []

    async def chat_with_search(self, *args, **kwargs):
        return json.dumps(self._research)

    async def chat(self, messages, **kwargs):
        # `messages` is the user-prompt list. Capture for assertions.
        prompt = messages[0]["content"] if messages else ""
        self.calls.append(prompt)
        # Deterministic body that satisfies the 65-120-word validator
        # so we don't trigger the retry path.
        # Long enough to clear the 65-word validator floor so the
        # personalizer doesn't trigger its retry path and burn an extra
        # chat() call we'd then have to subtract from our assertions.
        body = (
            "Priya, saw the Acme acquisition land last week and the enterprise hiring push. "
            "Most VPs in your seat juggle two motions at once when an acquisition closes: "
            "keeping the existing pipeline healthy while ramping new AEs against an unfamiliar ICP. "
            "We have helped revenue teams in similar spots after a merger cut the new-rep ramp gap "
            "by close to half within one quarter, with most of the work happening in week two and three "
            "after closing. Worth a quick look at the playbook?"
        )
        return json.dumps({
            "subject": f"Call {len(self.calls)}",
            "body": body,
            "word_count": len(body.split()),
            "anchor_signal": f"step-{len(self.calls)}",
        })


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


@pytest.mark.asyncio
async def test_sequence_length_generates_chain_with_distinct_angles():
    """sequence_length=3 should yield variation.sequence with 2 follow-up
    emails per variation, each generated from a step-specific prompt that
    includes the prior chain (so the model can pick a different angle)."""
    research = {
        "name": "Priya Sharma",
        "title": "VP Sales",
        "company": "Stripe",
        "industry": "Payments",
        "company_signals": ["Acquired Acme last week"],
        "individual_signals": ["Posted about RevOps"],
        "industry_trends": [],
        "role_pain_points": [],
        "strongest_trigger": "Recent Acme acquisition",
        "likely_pain_point": "Integrating new GTM motion",
    }

    from app.levels.schemas import VariationSpec
    brand = load_brand("lakeb2b")
    provider = SequenceMockProvider(research)
    # One variation × sequence_length=3 means: 1 initial + 2 follow-ups
    # = 3 chat() calls (the research call is chat_with_search, not chat).
    request = PersonalizeRequest(
        prospect=ProspectInput(name="Priya Sharma", title="VP Sales", domain="stripe.com"),
        sender=SenderInput(name="Subhakar", company="LakeB2B", offer="B2B data intelligence"),
        levels=[5],
        variations=[VariationSpec(slot="A", model="deepseek/deepseek-v4-pro", label="DeepSeek")],
        sequence_length=3,
    )
    response = await personalize(request, brand, provider)

    assert len(response.variations) == 1
    v = response.variations[0]
    # initial + 2 follow-ups
    assert v.email.subject == "Call 1"
    assert len(v.sequence) == 2, f"expected 2 follow-ups, got {len(v.sequence)}"
    assert v.sequence[0].subject == "Call 2"
    assert v.sequence[1].subject == "Call 3"
    # Back-compat property still works
    assert v.followup is not None
    assert v.followup.subject == "Call 2"

    # Three chat() calls: step 1 (initial) + step 2 + step 3.
    assert len(provider.calls) == 3
    # Step 2 prompt must mention "STEP 2" and the angle name
    assert "STEP 2" in provider.calls[1]
    assert "Bump with new angle" in provider.calls[1]
    # And it must include the initial email's subject as prior context
    assert "Call 1" in provider.calls[1]
    # Step 3 prompt must mention STEP 3 + the value-drop angle and see
    # BOTH prior emails (step 1 + step 2) in its context.
    assert "STEP 3" in provider.calls[2]
    assert "Value drop" in provider.calls[2]
    assert "Call 1" in provider.calls[2]
    assert "Call 2" in provider.calls[2]


@pytest.mark.asyncio
async def test_include_followup_back_compat_maps_to_sequence_2():
    """Old clients setting include_followup=True (no sequence_length)
    should still get exactly one follow-up — no behavior change."""
    research = {
        "name": "Priya Sharma", "title": "VP Sales", "company": "Stripe",
        "industry": "Payments",
        "company_signals": [], "individual_signals": [], "industry_trends": [],
        "role_pain_points": [], "strongest_trigger": "x", "likely_pain_point": "y",
    }

    from app.levels.schemas import VariationSpec
    brand = load_brand("lakeb2b")
    provider = SequenceMockProvider(research)
    request = PersonalizeRequest(
        prospect=ProspectInput(name="Priya Sharma", title="VP Sales", domain="stripe.com"),
        sender=SenderInput(name="Subhakar", company="LakeB2B", offer="B2B data intelligence"),
        levels=[5],
        variations=[VariationSpec(slot="A", model="deepseek/deepseek-v4-pro", label="DeepSeek")],
        include_followup=True,
        # sequence_length deliberately unset → defaults to 1
    )
    response = await personalize(request, brand, provider)
    v = response.variations[0]
    # include_followup=True should still yield exactly 1 follow-up
    # via the back-compat coercion in the personalizer.
    assert len(v.sequence) == 1
    assert v.followup is not None
    assert v.followup.subject == "Call 2"


@pytest.mark.asyncio
async def test_sequence_length_1_produces_no_followups():
    research = {
        "name": "x", "title": "y", "company": "z", "industry": "",
        "company_signals": [], "individual_signals": [], "industry_trends": [],
        "role_pain_points": [], "strongest_trigger": "", "likely_pain_point": "",
    }

    from app.levels.schemas import VariationSpec
    brand = load_brand("lakeb2b")
    provider = SequenceMockProvider(research)
    request = PersonalizeRequest(
        prospect=ProspectInput(name="x", title="y", domain="z.com"),
        sender=SenderInput(name="a", company="b", offer="c"),
        levels=[5],
        variations=[VariationSpec(slot="A", model="m", label="M")],
        # Both knobs at their defaults — no follow-ups expected.
    )
    response = await personalize(request, brand, provider)
    v = response.variations[0]
    assert v.sequence == []
    assert v.followup is None
    # Only the initial-email call should have happened.
    assert len(provider.calls) == 1
