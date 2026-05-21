"""Connectors for pushing personalized emails to downstream sequencers / CRMs.

Each connector exposes:

    class FooConnector:
        provider: str          # short identifier ("instantly", etc.)
        REQUIRED_FIELDS: tuple # config keys required at create-time

        async def push(self, config: dict, prospects_with_emails: list[dict]) -> PushResult
        async def healthcheck(self, config: dict) -> tuple[bool, str]

prospects_with_emails is the canonical payload:
    [
      {
        "name": "Priya Sharma",
        "title": "VP Sales",
        "domain": "stripe.com",
        "email": "priya@stripe.com",          # may be None
        "linkedin": "https://...",            # may be None
        "subject": "...",
        "body": "...",
        "followup_subject": "..." | None,
        "followup_body":    "..." | None,
        "model": "deepseek/deepseek-v4-pro",
        "slot": "A",
      }, ...
    ]

PushResult.ok is True iff every prospect was accepted (we surface
per-row errors so the UI can show which failed).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PushResult:
    ok: bool
    pushed: int
    failed: int
    errors: list[str] = field(default_factory=list)
    raw: dict | None = None
