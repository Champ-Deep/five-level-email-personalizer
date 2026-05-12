"""Faithful replica of the original artifact's prompts (Chief's claude.ai version).

Source: `~/Downloads/remixed-ef1d4c47.tsx`. The artifact calls
`api.anthropic.com/v1/messages` directly with `claude-sonnet-4-*` plus the
`web_search` tool. We reproduce the exact prompts here so the eval harness
can compute a faithful baseline on demand for any prospect — not just the
one captured manually from the live page.

Key fidelity points:

* System prompt is exactly what the artifact sends:
  "You are an elite B2B cold-email strategist. Return ONLY valid JSON …"
  — NO anti-slop layer, NO em-dash ban, NO 'not X but Y' detection.
* Buzzword list is the artifact's: synergy, leverage, streamline,
  game-changer, revolutionize. That's it.
* Sign-off rule per artifact: "Sign off: Best,\\n{sender.name}".
* L5 instruction is the artifact's verbatim weave-3-signals phrasing.

Use the same OpenRouter model the user's system uses (default
`anthropic/claude-sonnet-4.5`) so the comparison is fair.
"""

from __future__ import annotations

from app.levels.schemas import Brief, EmailDraft, ProspectInput, SenderInput
from app.services.llm.base import LLMProvider
from app.services.llm.openrouter import extract_json

CHIEF_SYSTEM = (
    "You are an elite B2B cold-email strategist. "
    "Return ONLY valid JSON — no markdown fences, no preamble, no explanation."
)


def _chief_research_prompt(p: ProspectInput) -> str:
    linkedin = str(p.linkedin) if p.linkedin else "not provided"
    return f"""Research this B2B prospect and return ONLY a JSON object.

PROSPECT:
- Name: {p.name}
- Title: {p.title}
- Company Domain: {p.domain}
- LinkedIn URL: {linkedin}

Use web search to find:
1. The actual company name from the domain
2. Recent company news, funding rounds, product launches, expansions, hiring signals (last 90 days)
3. If LinkedIn URL provided — recent posts, content themes, career changes of this individual
4. Industry vertical and key challenges for this sector
5. Role-level pain points common for someone with the title "{p.title}"

Return this exact JSON (no other text, no fences):
{{
  "name": "{p.name}",
  "title": "{p.title}",
  "company": "<company name>",
  "industry": "<detected vertical>",
  "companySignals": ["<signal 1>", "<signal 2>", "<signal 3>"],
  "individualSignals": ["<personal/LinkedIn signal 1>", "<signal 2>"],
  "industryTrends": ["<trend 1>", "<trend 2>"],
  "rolePainPoints": ["<pain for {p.title} 1>", "<pain 2>", "<pain 3>"],
  "strongestTrigger": "<single best opening hook — one sentence>",
  "likelyPainPoint": "<one-sentence hypothesis about their biggest problem right now>"
}}"""


def _chief_email_prompt(p: ProspectInput, s: SenderInput, b: Brief) -> str:
    sig = b.company_signals[0] if b.company_signals else b.strongest_trigger
    ind = b.individual_signals[0] if b.individual_signals else "their role transition"
    pain = b.role_pain_points[0] if b.role_pain_points else b.likely_pain_point
    return f"""
Write a cold outbound email for this prospect.

SENDER: {s.name} | {s.company}
OFFER: {s.offer}

PROSPECT: {p.name} | {p.title} at {b.company} ({b.industry})

INSTRUCTION: Write a Level 5 HYPER-PERSONALIZED email weaving together: company signal ("{sig}"), individual insight ("{ind}"), and role pain ("{pain}"). This email should feel written for this one human being, not a persona.

STRICT RULES — no exceptions:
- Subject line: max 8 words, no questions, no clickbait, no ALL CAPS
- Body: 65–120 words, plain prose, NO bullets, NO lists, NO formatting
- One CTA only: a soft permission-ask ("Worth a quick look?") — never "Book a demo" or "Click here"
- NO links, NO images, NO HTML
- Greet by first name only
- No filler openers ("Hope this finds you", "I wanted to reach out")
- No buzzwords: synergy, leverage, streamline, game-changer, revolutionize
- Sign off: Best,\\n{s.name}

Return ONLY this JSON (no fences, no explanation):
{{
  "subject": "<subject line>",
  "body": "<email body — plain prose>",
  "wordCount": <integer>,
  "anchorSignal": "<the one signal this email pivots on>"
}}"""


def _normalize_brief(data: dict, p: ProspectInput) -> dict:
    aliases = {
        "companySignals": "company_signals",
        "individualSignals": "individual_signals",
        "industryTrends": "industry_trends",
        "rolePainPoints": "role_pain_points",
        "strongestTrigger": "strongest_trigger",
        "likelyPainPoint": "likely_pain_point",
    }
    out = {aliases.get(k, k): v for k, v in data.items()}
    out.setdefault("name", p.name)
    out.setdefault("title", p.title)
    return out


def _normalize_email(data: dict) -> dict:
    aliases = {"wordCount": "word_count", "anchorSignal": "anchor_signal"}
    return {aliases.get(k, k): v for k, v in data.items()}


async def chief_baseline_email(
    prospect: ProspectInput,
    sender: SenderInput,
    provider: LLMProvider,
    model: str,
) -> tuple[Brief, EmailDraft]:
    """Run the artifact's exact two-phase flow: research → L5 hyper email."""
    research_raw = await provider.chat_with_search(
        [{"role": "user", "content": _chief_research_prompt(prospect)}],
        model=model,
        max_tokens=2000,
        temperature=0.4,
        system=CHIEF_SYSTEM,
    )
    brief = Brief(**_normalize_brief(extract_json(research_raw), prospect))

    email_raw = await provider.chat(
        [{"role": "user", "content": _chief_email_prompt(prospect, sender, brief)}],
        model=model,
        max_tokens=900,
        temperature=0.7,
        system=CHIEF_SYSTEM,
    )
    data = _normalize_email(extract_json(email_raw))
    draft = EmailDraft(
        subject=str(data.get("subject", "")).strip(),
        body=str(data.get("body", "")).strip(),
        word_count=int(data.get("word_count") or 0),
        anchor_signal=str(data.get("anchor_signal", "")).strip(),
    )
    return brief, draft
