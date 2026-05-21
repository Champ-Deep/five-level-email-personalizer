"""Suppression list matching service.

A prospect is "suppressed" if their email OR their domain matches any
entry in the caller's suppression list. Matching:

  email match  — exact, case-insensitive on the local part too
  domain match — exact-suffix on the domain (so "stripe.com" matches
                 "priya@stripe.com" AND "support.stripe.com")

The full list is loaded per-batch (one query) and matched in-memory.
For users with very large suppression lists this could move to a
Bloom filter or Postgres LIKE, but 50k entries fit comfortably.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SuppressionEntry


class SuppressionMatcher:
    def __init__(self, emails: set[str], domains: list[str]) -> None:
        self._emails = emails
        # Sort domains by length descending so exact "foo.bar.com" matches
        # before its parent "bar.com" would, in case both are present.
        self._domains = sorted(domains, key=len, reverse=True)

    def reason_for(self, email: str | None, domain: str | None) -> str | None:
        """Return None if not suppressed; otherwise a short reason string."""
        if email:
            e = email.strip().lower()
            if e in self._emails:
                return "email on suppression list"
            # Extract domain from the email if no explicit domain field was given.
            if not domain and "@" in e:
                domain = e.split("@", 1)[1]
        if domain:
            d = domain.strip().lower().lstrip(".")
            for s in self._domains:
                if d == s or d.endswith("." + s):
                    return f"domain '{s}' on suppression list"
        return None


async def load_matcher(session: AsyncSession, owner_sub: str) -> SuppressionMatcher:
    rows = (
        await session.execute(
            select(SuppressionEntry).where(SuppressionEntry.owner_email == owner_sub)
        )
    ).scalars().all()
    emails = {r.email.lower() for r in rows if r.email}
    domains = [r.domain.lower().lstrip(".") for r in rows if r.domain]
    return SuppressionMatcher(emails=emails, domains=domains)
