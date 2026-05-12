from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    word_count: int = 0
    anchor_signal: str = ""
    warnings: list[str] = Field(default_factory=list)


class PersonalizeResult(BaseModel):
    brand: str
    brief: Brief
    emails: dict[int, EmailDraft]


class JobStatus(BaseModel):
    job_id: str
    status: str
    brand: str
    total: int
    done: int
    failed_count: int
    live: dict[str, Any] = Field(default_factory=dict)
    results: dict[int, Any] = Field(default_factory=dict)


class BatchResult(BaseModel):
    job_id: str
