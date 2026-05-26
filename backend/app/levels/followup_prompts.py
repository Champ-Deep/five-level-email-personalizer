"""Sequence prompt builder.

A sequence is the initial email + 0-4 follow-ups. Each follow-up has a
distinct *angle* so a 5-touch sequence doesn't read as repetitive:

  Step 2 — Bump w/ new angle.       Extend the original anchor signal.
  Step 3 — Value drop.              Useful insight or resource.
  Step 4 — Social proof.            Similar customer / outcome.
  Step 5 — Breakup.                 "Should I close the loop?"

Each step's prompt feeds in the full prior chain so the model can avoid
repeating any earlier subject lines, anchor signals, or body framings.

The original `followup_prompt(brief, sender, initial)` entrypoint is
kept as a back-compat shim that calls `sequence_step_prompt(step=2, …)`
with `prior_emails=[initial]`.
"""

from __future__ import annotations

from app.levels.schemas import Brief, EmailDraft, SenderInput


# Per-step angle config. Each tuple is (intent, body length guidance,
# subject hint). Steps 6+ fall back to the "breakup" template — no
# legitimate B2B sequence runs longer than 5 touches.
_STEP_ANGLES: dict[int, dict[str, str]] = {
    2: {
        "name": "Bump with new angle",
        "intent": (
            "Re-earn attention with a NEW concrete extension of the initial anchor "
            "(a new data point, a counter-example, a question that probes deeper). "
            "NOT a recap, NOT 'bumping this'."
        ),
        "body_words": "50-75",
        "subject_hint": "max 7 words, no questions, no 'Re:', no 'Following up'",
    },
    3: {
        "name": "Value drop",
        "intent": (
            "Drop a specific, useful piece of value — a stat, a framework, a "
            "comparison, a 1-line insight from the industry — that they'd find "
            "interesting EVEN IF they never reply. No ask in the body, only a "
            "soft mention of the offer at the end."
        ),
        "body_words": "60-85",
        "subject_hint": "max 8 words, can hint at the value drop (e.g. 'One data point on X')",
    },
    4: {
        "name": "Social proof",
        "intent": (
            "Reference a SIMILAR company (same industry segment, same role profile, "
            "or same trigger as the prospect's strongest_trigger) and a concrete "
            "outcome they got. Brief, specific, no name-drop fluff."
        ),
        "body_words": "60-85",
        "subject_hint": "max 8 words, can name-drop the peer-company pattern (e.g. 'How [similar company] approached X')",
    },
    5: {
        "name": "Breakup",
        "intent": (
            "Friendly final touch. Acknowledge they're probably busy or this isn't "
            "a fit right now. Give them a graceful out ('Want me to close the "
            "loop?'). NO new pitch, NO new value drop — this is just an explicit "
            "permission-to-stop-emailing."
        ),
        "body_words": "30-50",
        "subject_hint": "max 7 words, can be direct (e.g. 'Closing the loop?', 'Last note')",
    },
}


def sequence_step_prompt(
    *,
    step: int,
    brief: Brief,
    sender: SenderInput,
    prior_emails: list[EmailDraft],
) -> str:
    """Build the LLM prompt for follow-up step N.

    `step` is 2-based: step 2 is the first follow-up (the initial email
    is step 1 and never goes through this builder). `prior_emails`
    contains the initial email plus any follow-ups already generated,
    in order. The model sees all of them as 'context, do not repeat'.
    """
    if step < 2:
        raise ValueError(f"sequence_step_prompt only handles step >= 2 (got {step})")
    angle = _STEP_ANGLES.get(step, _STEP_ANGLES[5])  # 6+ falls back to breakup

    # Render the prior chain inline. Truncate each body so the prompt
    # stays well under the model's effective context window even for
    # long sequences.
    chain_blocks: list[str] = []
    for idx, e in enumerate(prior_emails, start=1):
        chain_blocks.append(
            f"  Step {idx} subject: {e.subject}\n"
            f"  Step {idx} anchor:  {e.anchor_signal}\n"
            f"  Step {idx} body:    {e.body[:500]}"
        )
    chain = "\n\n".join(chain_blocks) if chain_blocks else "  (none)"

    return f"""Write follow-up email STEP {step} ({angle['name']}) for this prospect.

PROSPECT: {brief.name} | {brief.title} at {brief.company} ({brief.industry})
SENDER:   {sender.name} | {sender.company}
OFFER:    {sender.offer}

PRIOR EMAILS IN THIS SEQUENCE (already sent — do NOT repeat their subjects, anchors, or framings):
{chain}

YOUR JOB FOR STEP {step}:
{angle['intent']}

STRICT RULES — no exceptions:
- Subject line: {angle['subject_hint']}
- Body: {angle['body_words']} words, plain prose
- Greet by first name only
- No filler openers ("Just checking in", "Bumping this", "Wanted to follow up", "Bringing this back to your inbox", "Hope this finds you well")
- No buzzwords (delve / leverage / streamline / navigate / robust / holistic / seamless / supercharge / paradigm / transformative / cutting-edge)
- No em-dashes, no en-dashes
- No "not X, but Y" constructions
- Sign off: Best,\\n{sender.name}

Return ONLY this JSON (no fences, no explanation):
{{
  "subject": "<subject line>",
  "body": "<email body — plain prose>",
  "word_count": <integer>,
  "anchor_signal": "<the angle this step pivots on (specific to step {step})>"
}}"""


def followup_prompt(
    brief: Brief,
    sender: SenderInput,
    initial: EmailDraft,
) -> str:
    """Back-compat shim. Old callers that only knew about a single
    follow-up still hit this function; we treat it as step 2.
    """
    return sequence_step_prompt(
        step=2,
        brief=brief,
        sender=sender,
        prior_emails=[initial],
    )
