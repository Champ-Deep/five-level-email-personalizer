"""ICP-fit scoring.

Given a saved ICP description and a researched Brief, ask the LLM to
score the prospect 0-100 with a one-sentence reason. Runs as a fast
sidecar call before the main personalize path so callers can filter
out poor-fit prospects without burning tokens on personalization.

The scoring model defaults to a small fast model (Llama 4 Maverick) but
is configurable. The prompt is tight to keep cost down (~200 tokens out).
"""

from __future__ import annotations

from app.levels.schemas import Brief, ProspectInput
from app.services.llm.base import LLMProvider
from app.services.llm.openrouter import extract_json


def _icp_prompt(prospect: ProspectInput, brief: Brief | None, icp_description: str) -> str:
    company_facts = ""
    if brief:
        company_facts = (
            f"  industry: {brief.industry}\n"
            f"  company: {brief.company}\n"
            f"  company_signals: {brief.company_signals[:3]}\n"
            f"  individual_signals: {brief.individual_signals[:2]}\n"
        )
    return f"""You score how well a B2B prospect fits a target ICP description.

ICP description (what the ideal customer looks like):
{icp_description.strip()}

PROSPECT:
  name:   {prospect.name}
  title:  {prospect.title}
  domain: {prospect.domain}
{company_facts}

SCORE THE FIT 0-100:
  90-100  perfect fit, top priority
  70-89   strong fit, prioritize
  40-69   marginal fit, deprioritize
  0-39    poor fit, skip

Return ONLY this JSON (no fences, no preamble):
{{
  "score": <integer 0-100>,
  "reason": "<one sentence, 15-25 words, specific>"
}}"""


async def score_icp_fit(
    prospect: ProspectInput,
    icp_description: str,
    provider: LLMProvider,
    model: str = "meta-llama/llama-4-maverick",
    brief: Brief | None = None,
) -> dict:
    raw = await provider.chat(
        [{"role": "user", "content": _icp_prompt(prospect, brief, icp_description)}],
        model=model,
        max_tokens=400,
        temperature=0.2,
        system="You are a precise B2B sales analyst. Return ONLY valid JSON.",
    )
    data = extract_json(raw)
    score = max(0, min(100, int(data.get("score", 0))))
    return {"score": score, "reason": str(data.get("reason", "")).strip()}
