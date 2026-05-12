"""Prompt builders for the 5-Level personalizer.

Ported from the React artifact (`~/Downloads/remixed-ef1d4c47.tsx`, lines 305-381).
The STRICT RULES block is verbatim — it's the spine of the framework.
"""

from __future__ import annotations

from app.levels.definitions import level_meta
from app.levels.schemas import Brief, ProspectInput, SenderInput


SYSTEM_PROMPT_BASE = (
    "You are an elite B2B cold-email strategist. "
    "Return ONLY valid JSON — no markdown fences, no preamble, no explanation."
)


def system_prompt(brand_addendum: str | None) -> str:
    if not brand_addendum:
        return SYSTEM_PROMPT_BASE
    return f"{SYSTEM_PROMPT_BASE}\n\nBrand voice:\n{brand_addendum.strip()}"


def research_prompt(prospect: ProspectInput) -> str:
    linkedin = str(prospect.linkedin) if prospect.linkedin else "not provided"
    return f"""Research this B2B prospect and return ONLY a JSON object.

PROSPECT:
- Name: {prospect.name}
- Title: {prospect.title}
- Company Domain: {prospect.domain}
- LinkedIn URL: {linkedin}

Use web search to find:
1. The actual company name from the domain
2. Recent company news, funding rounds, product launches, expansions, hiring signals (last 90 days)
3. If LinkedIn URL provided — recent posts, content themes, career changes of this individual
4. Industry vertical and key challenges for this sector
5. Role-level pain points common for someone with the title "{prospect.title}"

Return this exact JSON (no other text, no fences):
{{
  "name": "{prospect.name}",
  "title": "{prospect.title}",
  "company": "<company name>",
  "industry": "<detected vertical>",
  "company_signals": ["<signal 1>", "<signal 2>", "<signal 3>"],
  "individual_signals": ["<personal/LinkedIn signal 1>", "<signal 2>"],
  "industry_trends": ["<trend 1>", "<trend 2>"],
  "role_pain_points": ["<pain for {prospect.title} 1>", "<pain 2>", "<pain 3>"],
  "strongest_trigger": "<single best opening hook — one sentence>",
  "likely_pain_point": "<one-sentence hypothesis about their biggest problem right now>"
}}"""


def _level_instruction(level: int, brief: Brief, prospect_title: str) -> str:
    first_company_signal = brief.company_signals[0] if brief.company_signals else brief.strongest_trigger
    second_company_signal = brief.company_signals[1] if len(brief.company_signals) > 1 else first_company_signal
    first_individual = brief.individual_signals[0] if brief.individual_signals else "their recent role transition"
    first_pain = brief.role_pain_points[0] if brief.role_pain_points else brief.likely_pain_point

    if level == 1:
        return (
            f"Write a Level 1 cold email using ONLY a broad industry trend — no company name, "
            f"no personal details. The insight should apply to any {brief.industry} company with a {prospect_title}."
        )
    if level == 2:
        return (
            f'Write a Level 2 cold email anchored to ONE specific company signal: "{first_company_signal}". '
            f"Make them feel you tracked their company, not just Googled them."
        )
    if level == 3:
        return (
            f"Write a Level 3 cold email focused on the ROLE pain points of a {prospect_title}. "
            f'No personal details. Pure title-function resonance. Pain: "{first_pain}"'
        )
    if level == 4:
        anchor = brief.individual_signals[0] if brief.individual_signals else second_company_signal
        return (
            f'Write a Level 4 cold email referencing an INDIVIDUAL signal about {brief.name}: "{anchor}". '
            f"Make them feel genuinely seen."
        )
    if level == 5:
        return (
            f"Write a Level 5 HYPER-PERSONALIZED email weaving together: "
            f'company signal ("{first_company_signal}"), individual insight ("{first_individual}"), '
            f'and role pain ("{first_pain}"). This email should feel written for this one human being, not a persona.'
        )
    raise ValueError(f"Unknown level: {level}")


def email_prompt(
    level: int,
    brief: Brief,
    sender: SenderInput,
    prospect_title: str,
) -> str:
    meta = level_meta(level)
    instruction = _level_instruction(level, brief, prospect_title)
    return f"""Write a cold outbound email for this prospect.

SENDER: {sender.name} | {sender.company}
OFFER: {sender.offer}

PROSPECT: {brief.name} | {brief.title} at {brief.company} ({brief.industry})

LEVEL {meta.id} — {meta.label}
PREMISE: {meta.premise}

INSTRUCTION: {instruction}

STRICT RULES — no exceptions:
- Subject line: max 8 words, no questions, no clickbait, no ALL CAPS
- Body: 65–120 words, plain prose, NO bullets, NO lists, NO formatting
- One CTA only: a soft permission-ask ("Worth a quick look?") — never "Book a demo" or "Click here"
- NO links, NO images, NO HTML
- Greet by first name only
- No filler openers ("Hope this finds you", "I wanted to reach out")
- No buzzwords: synergy, leverage, streamline, game-changer, revolutionize
- Sign off: Best,\\n{sender.name}

Return ONLY this JSON (no fences, no explanation):
{{
  "subject": "<subject line>",
  "body": "<email body — plain prose>",
  "word_count": <integer>,
  "anchor_signal": "<the one signal this email pivots on>"
}}"""


BANNED_WORDS: tuple[str, ...] = (
    "synergy",
    "synergies",
    "leverage",
    "leveraging",
    "streamline",
    "streamlining",
    "game-changer",
    "game changer",
    "revolutionize",
    "revolutionise",
    "hope this finds you",
    "wanted to reach out",
)
