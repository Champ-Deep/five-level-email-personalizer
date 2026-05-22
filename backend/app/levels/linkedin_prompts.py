"""LinkedIn DM prompt builder.

LinkedIn DMs ride on the same 5-layer pipeline as the email, but they
follow different rules:

  - HARD LIMIT 300 characters (LinkedIn collapses anything longer in
    the preview — recipients won't read past the fold).
  - No subject line (the platform doesn't show one).
  - No "Best, <name>" sign-off (the message bubble already shows your
    avatar + name).
  - Single CTA, but soften it more than email — LinkedIn etiquette
    rewards "curious to swap notes" framings over hard meeting asks.
  - The anchor signal must show up in the FIRST 50 characters or the
    DM looks templated.

We deliberately keep the same JSON shape (`body`, `char_count`,
`anchor_signal`) as the EmailDraft for two reasons: the validator can
be reused for the anti-slop pass, and the frontend can render either
output with the same component.
"""

from __future__ import annotations

from app.levels.schemas import Brief, EmailDraft, SenderInput


def linkedin_prompt(brief: Brief, sender: SenderInput, initial: EmailDraft | None = None) -> str:
    """Build the LLM prompt that produces a LinkedIn DM.

    `initial` is the email already generated for the same prospect. If
    present we hand it to the model so the DM reaches for a DIFFERENT
    angle on the same anchor signal — otherwise the prospect gets two
    copies of the same message across channels.
    """
    initial_section = ""
    if initial:
        initial_section = (
            "\n\nThe EMAIL you already wrote for this prospect is below. "
            "Your LinkedIn DM should hit the SAME anchor signal but with a "
            "different opener and a slightly different angle — the prospect "
            "will see both messages.\n"
            f"---EMAIL START---\nSubject: {initial.subject}\n\n{initial.body}\n---EMAIL END---"
        )

    return f"""Write a LinkedIn DM for this prospect.

PROSPECT
  Name: {brief.name}
  Title: {brief.title}
  Company: {brief.company}
  Industry: {brief.industry}

SIGNALS YOU CAN USE
  Company: {", ".join(brief.company_signals) or "—"}
  Individual: {", ".join(brief.individual_signals) or "—"}
  Industry trends: {", ".join(brief.industry_trends) or "—"}
  Role pains: {", ".join(brief.role_pain_points) or "—"}
  Strongest trigger: {brief.strongest_trigger or "—"}

SENDER
  {sender.name} at {sender.company}
  Offer: {sender.offer}

HARD RULES
  - MAX 300 CHARACTERS total. LinkedIn collapses anything longer; the
    recipient won't scroll. Count carefully.
  - No subject line, no "Best, …" sign-off, no signature.
  - The anchor signal MUST appear in the first 50 characters.
  - One soft CTA. Acceptable patterns: "curious whether you've thought
    about X?", "open to swapping notes?", "happy to share what we're
    seeing if useful." Unacceptable: "let's hop on a call", "grab 15
    min on my calendar".
  - No em-dashes. Use commas or periods.
  - No buzzwords: synergy, leverage, streamline, game-changer,
    revolutionize, seamless, transformative, robust, cutting-edge,
    next-gen, paradigm, ecosystem, holistic, scalable.
  - No "not X, but Y" constructions.
  - First-person, plain English. Sound like a peer reaching out, not a
    vendor pitching.
{initial_section}

OUTPUT — return ONLY this JSON shape, nothing before or after:
{{
  "body": "<the LinkedIn DM, 300 chars or less>",
  "char_count": <integer count of characters in body>,
  "anchor_signal": "<the one specific signal you anchored the DM to>"
}}
"""
