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

    def as_full_text(self, sender_name: str) -> str:
        return f"Subject: {self.subject}\n\n{self.body}\n\nBest,\n{sender_name}"


class LeveledEmail(BaseModel):
    level: int
    email: EmailDraft


class PersonalizeRequest(BaseModel):
    prospect: ProspectInput
    sender: Optional[SenderInput] = None
    levels: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    provider: str = "openrouter"
    model: Optional[str] = None
    system_prompt_override: Optional[str] = None
    style_rules: Optional[str] = Field(
        default=None,
        description="Free-text additional style rules from the caller. Appended to the brand voice; does NOT replace it.",
    )


class PersonalizeResponse(BaseModel):
    brand: str
    brief: Brief
    emails: dict[int, EmailDraft]


class BatchPersonalizeRequest(BaseModel):
    prospects: list[ProspectInput]
    sender: Optional[SenderInput] = None
    levels: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    provider: str = "openrouter"
    model: Optional[str] = None
    system_prompt_override: Optional[str] = None
    style_rules: Optional[str] = None
