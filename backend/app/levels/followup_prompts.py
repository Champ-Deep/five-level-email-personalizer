"""Follow-up email prompt builder.

The follow-up is sent 3-5 days after the initial outreach if no reply.
It MUST:
  - Reference the original anchor signal (otherwise it reads like spam)
  - Add a new value drop or different angle, never just "bumping this"
  - Stay under 75 words (shorter than the initial)
  - Use the same brand voice + style rules + anti-slop ruleset
  - End with the same soft permission-ask

This module mirrors the structure of `prompts.py` (initial email) so
the same validator + retry path can be reused unchanged.
"""

from __future__ import annotations

from app.levels.schemas import Brief, EmailDraft, SenderInput


def followup_prompt(
    brief: Brief,
    sender: SenderInput,
    initial: EmailDraft,
) -> str:
    """Build the LLM prompt that produces the follow-up email.

    Includes the initial email's anchor + body so the model has the
    context to write a continuation that doesn't repeat.
    """
    return f"""Write a short FOLLOW-UP email for this prospect.

Sent 3-5 days after the initial outreach if no reply. The job is to
re-earn attention with a NEW angle, not to nag.

PROSPECT: {brief.name} | {brief.title} at {brief.company} ({brief.industry})
SENDER:   {sender.name} | {sender.company}
OFFER:    {sender.offer}

INITIAL EMAIL CONTEXT (already sent — do NOT repeat its content):
  Subject: {initial.subject}
  Anchor:  {initial.anchor_signal}
  Body:    {initial.body[:600]}

WRITE A FOLLOW-UP THAT:
1. Opens with ONE concrete extension of the initial anchor (a new data
   point, a counter-example, a question that probes deeper), NOT a recap.
2. Adds a single new value drop — a fact, framing, or peer comparison
   that's distinct from the initial. NO "circling back" / "bumping this".
3. Ends with the same soft permission-ask used in the initial email
   ("Worth a quick look?").

STRICT RULES — no exceptions:
- Subject line: max 7 words, no questions, no "Re:", no "Following up"
- Body: 50-75 words, plain prose
- Greet by first name only
- No filler openers ("Just checking in", "Bumping this", "Wanted to follow up", "Bringing this back to your inbox")
- No buzzwords (delve / leverage / streamline / navigate / robust / holistic / seamless / supercharge / paradigm / transformative / cutting-edge)
- No em-dashes, no en-dashes
- No "not X, but Y" constructions
- Sign off: Best,\\n{sender.name}

Return ONLY this JSON (no fences, no explanation):
{{
  "subject": "<subject line>",
  "body": "<email body — plain prose>",
  "word_count": <integer>,
  "anchor_signal": "<the new angle this follow-up pivots on>"
}}"""
