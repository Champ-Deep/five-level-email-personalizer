from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ProspectInput(BaseModel):
    name: str
    title: str
    domain: str
    linkedin: Optional[HttpUrl] = None
    email: Optional[EmailStr] = None


class SenderInput(BaseModel):
    name: str
    company: str
    offer: str = Field(..., max_length=600)


class Brief(BaseModel):
    name: str
    title: str
    company: str
    industry: str = ""
    company_signals: list[str] = Field(default_factory=list)
    individual_signals: list[str] = Field(default_factory=list)
    industry_trends: list[str] = Field(default_factory=list)
    role_pain_points: list[str] = Field(default_factory=list)
    strongest_trigger: str = ""
    likely_pain_point: str = ""


class EmailDraft(BaseModel):
    subject: str
    body: str
    word_count: int
    anchor_signal: str
    warnings: list[str] = Field(default_factory=list)
    scores: Optional[dict] = Field(
        default=None,
        description="{deliverability: {score, factors}, reply_likelihood: {score, factors}}",
    )

    def as_full_text(self, sender_name: str) -> str:
        return f"Subject: {self.subject}\n\n{self.body}\n\nBest,\n{sender_name}"


class LinkedInDraft(BaseModel):
    """LinkedIn DM rendering of the same 5-layer pipeline.

    LinkedIn DMs land best when they're conversational, ≤300 chars, and
    skip the email signature/CTA conventions. We keep this shape close to
    `EmailDraft` so the UI can render either with the same component."""
    body: str
    char_count: int
    anchor_signal: str
    warnings: list[str] = Field(default_factory=list)


class LeveledEmail(BaseModel):
    level: int
    email: EmailDraft


class VariationSpec(BaseModel):
    slot: str = Field(..., description="Stable identifier (A, B, C, …)")
    model: str = Field(..., description="OpenRouter model slug")
    label: str = Field("", description="Human-readable name shown in the UI")


class Variation(BaseModel):
    slot: str
    label: str
    model: str
    email: EmailDraft
    followup: Optional[EmailDraft] = Field(
        default=None,
        description="Optional follow-up email, generated when include_followup=true on the request.",
    )
    linkedin: Optional[LinkedInDraft] = Field(
        default=None,
        description="Optional LinkedIn DM, generated when include_linkedin=true on the request.",
    )


class PersonalizeRequest(BaseModel):
    prospect: ProspectInput
    sender: Optional[SenderInput] = None
    levels: list[int] = Field(default_factory=lambda: [5])
    provider: str = "openrouter"
    model: Optional[str] = Field(
        default=None,
        description="Single-model legacy path. If `variations` is set, this is ignored.",
    )
    variations: Optional[list[VariationSpec]] = Field(
        default=None,
        description="When set, generate one fused-5-layer email per variation. Defaults to env-configured A/B/C slots.",
    )
    system_prompt_override: Optional[str] = None
    style_rules: Optional[str] = Field(
        default=None,
        description="Free-text additional style rules from the caller. Appended to the brand voice; does NOT replace it.",
    )
    tone_preset: Optional[str] = Field(
        default=None,
        description="One of: casual, formal, founder, friendly, concise. Composed into style_rules.",
    )
    include_followup: bool = Field(
        default=False,
        description="Generate a follow-up email per variation (additional LLM call per variation).",
    )
    include_linkedin: bool = Field(
        default=False,
        description="Generate a sub-300-char LinkedIn DM per variation (additional LLM call per variation, same model).",
    )
    icp_profile_id: Optional[str] = Field(
        default=None,
        description="If set, score the prospect against this saved ICP profile and include the score in the response.",
    )
    icp_description: Optional[str] = Field(
        default=None,
        description="Ad-hoc ICP description (free text). Used if icp_profile_id is not set.",
    )


class IcpFit(BaseModel):
    score: int  # 0-100
    reason: str
    profile_id: Optional[str] = None


class PersonalizeResponse(BaseModel):
    brand: str
    brief: Brief
    variations: list[Variation] = Field(default_factory=list)
    icp_fit: Optional[IcpFit] = None
    # `emails` kept for backward compat with single-model callers (eval harness, SDK).
    # Populated with one entry keyed by the highest level requested, using slot A.
    emails: dict[int, EmailDraft] = Field(default_factory=dict)


class BatchPersonalizeRequest(BaseModel):
    prospects: list[ProspectInput]
    sender: Optional[SenderInput] = None
    levels: list[int] = Field(default_factory=lambda: [5])
    provider: str = "openrouter"
    model: Optional[str] = None
    variations: Optional[list[VariationSpec]] = None
    system_prompt_override: Optional[str] = None
    style_rules: Optional[str] = None
    tone_preset: Optional[str] = None
    include_followup: bool = False
    include_linkedin: bool = False
