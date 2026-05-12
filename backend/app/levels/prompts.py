"""Prompt builders for the 5-Level personalizer.

Ported from the React artifact (`~/Downloads/remixed-ef1d4c47.tsx`, lines 305-381).
The STRICT RULES block is verbatim — it's the spine of the framework.
"""

from __future__ import annotations

from app.levels.definitions import level_meta
from app.levels.schemas import Brief, ProspectInput, SenderInput


SYSTEM_PROMPT_BASE = (
    "You are an elite B2B cold-email strategist. "
    "Return ONLY valid JSON. No markdown fences, no preamble, no explanation."
)

# Hard rules that apply to EVERY call, regardless of brand or user override.
# Designed to strip the most common "AI sounds like AI" tells.
ANTI_SLOP_RULES = """\
Hard writing rules (every email, no exceptions):

1. NO em-dashes (—). Use commas, periods, or em-dash-free phrasing instead. \
Hyphens between words ("data-driven") are fine. An en-dash or em-dash is not.
2. NO "not X, but Y" or "it's not just X, it's Y" constructions. These are the single biggest AI tell. \
Rewrite as a direct statement.
3. NO AI-slop vocabulary: delve, leverage, leveraging, navigate, navigating, \
landscape, ecosystem (unless the prospect literally builds one), tapestry, realm, \
robust, comprehensive, holistic, seamless, seamlessly, unlock, unlocking, empower, \
empowering, supercharge, supercharging, game-changer, game-changing, paradigm, \
streamline, streamlining, synergy, synergistic, revolutionize, revolutionise, \
transformative, transformational, cutting-edge, best-in-class, world-class, \
in today's fast-paced world, in today's rapidly evolving.
4. NO opener clichés: "hope this finds you", "I wanted to reach out", \
"I came across your", "I noticed that you", "I hope you're doing well", "quick question".
5. NO marketing throat-clearing: "I'll be brief", "I'll keep this short", \
"long story short", "to be honest", "frankly".
6. NO em-dashes again (it bears repeating because models love them).
7. Plain prose only. Short sentences over long ones. Use specific concrete nouns \
(Stripe's Dublin office, Series B, March launch) rather than abstract ones."""


def system_prompt(
    brand_addendum: str | None = None,
    style_rules: str | None = None,
) -> str:
    """Compose the full system prompt: base + hard anti-slop rules + brand voice + user rules.

    All three layers are additive — `style_rules` does NOT replace the brand voice.
    """
    parts = [SYSTEM_PROMPT_BASE, ANTI_SLOP_RULES]
    if brand_addendum and brand_addendum.strip():
        parts.append(f"Brand voice:\n{brand_addendum.strip()}")
    if style_rules and style_rules.strip():
        parts.append(f"Additional caller-provided rules (must override anything that conflicts above):\n{style_rules.strip()}")
    return "\n\n".join(parts)


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
        industry_trend = brief.industry_trends[0] if brief.industry_trends else f"recent shifts in {brief.industry}"
        return (
            "Write ONE hyper-personalized email that FUSES ALL FIVE signal layers into a single, cohesive message. "
            "The email must explicitly weave together every layer below — not skip any, not bullet them, not "
            "stack them, but synthesize them into one continuous argument:\n\n"
            f"  · INDUSTRY layer (the macro context): \"{industry_trend}\"\n"
            f"  · COMPANY layer (something specific to {brief.company}): \"{first_company_signal}\"\n"
            f"  · ROLE layer (a pressure specific to a {prospect_title}): \"{first_pain}\"\n"
            f"  · INDIVIDUAL layer (something about {brief.name} personally): \"{first_individual}\"\n"
            f"  · HYPER layer (your synthesized POV / hypothesis): \"{brief.likely_pain_point}\"\n\n"
            "Open with the individual or company layer — never with industry generalities. Build a hypothesis "
            "in the middle that ties them together. End with the soft permission-ask. The email should read as "
            "one human writing to one specific human, not a templated drip. ALL FIVE layers must be observably "
            "present in the final email."
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
    # Existing
    "synergy", "synergies", "leverage", "leveraging",
    "streamline", "streamlining", "game-changer", "game changer",
    "revolutionize", "revolutionise",
    "hope this finds you", "wanted to reach out",
    # AI-slop vocabulary
    "delve", "navigate", "navigating", "landscape", "tapestry", "realm",
    "robust", "comprehensive", "holistic", "seamless", "seamlessly",
    "unlock", "unlocking", "empower", "empowering",
    "supercharge", "supercharging", "paradigm",
    "transformative", "transformational",
    "cutting-edge", "best-in-class", "world-class",
    # Opener clichés
    "i came across your", "i noticed that you", "hope you're doing well",
    "quick question", "i'll be brief", "i'll keep this short",
    "long story short", "to be honest", "frankly,",
    "in today's fast-paced", "in today's rapidly evolving",
)

# Em-dash characters (NOT hyphen-minus). Includes em-dash and en-dash.
EM_DASH_CHARS: tuple[str, ...] = ("—", "–")

# "Not X, but Y" / "It's not just X, it's Y" pattern detection.
# Catches the most common AI cliché construction.
NOT_X_BUT_Y_PATTERNS: tuple[str, ...] = (
    r"\bnot\s+(?:just\s+)?[^.,;]{1,40},\s+but\b",
    r"\bit's\s+not\s+(?:just\s+)?[^.,;]{1,40},?\s+it's\b",
    r"\bit\s+is\s+not\s+(?:just\s+)?[^.,;]{1,40},?\s+it\s+is\b",
)
