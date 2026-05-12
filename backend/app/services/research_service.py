from app.core.config import get_settings
from app.levels.prompts import research_prompt, system_prompt
from app.levels.schemas import Brief, ProspectInput
from app.services.llm.base import LLMProvider
from app.services.llm.openrouter import extract_json


async def research_prospect(
    prospect: ProspectInput,
    provider: LLMProvider,
    brand_addendum: str | None = None,
) -> Brief:
    settings = get_settings()
    prompt = research_prompt(prospect)
    raw = await provider.chat_with_search(
        [{"role": "user", "content": prompt}],
        model=settings.openrouter_research_model,
        max_tokens=2000,
        temperature=0.4,
        system=system_prompt(brand_addendum),
    )
    try:
        data = extract_json(raw)
    except Exception:
        # One retry: ask for valid JSON only, without web search this time.
        raw = await provider.chat(
            [
                {"role": "user", "content": prompt},
                {"role": "user", "content": "Your previous response could not be parsed as JSON. Return ONLY the JSON object — no preamble, no code fences, no smart quotes, no trailing commas."},
            ],
            model=settings.openrouter_default_model,
            max_tokens=2000,
            temperature=0.2,
            system=system_prompt(brand_addendum),
        )
        data = extract_json(raw)
    return Brief(**_normalize(data, prospect))


def _normalize(data: dict, prospect: ProspectInput) -> dict:
    """LLMs sometimes camelCase keys; map them back to our snake_case schema."""
    aliases = {
        "companySignals": "company_signals",
        "individualSignals": "individual_signals",
        "industryTrends": "industry_trends",
        "rolePainPoints": "role_pain_points",
        "strongestTrigger": "strongest_trigger",
        "likelyPainPoint": "likely_pain_point",
    }
    out = {}
    for k, v in data.items():
        out[aliases.get(k, k)] = v
    out.setdefault("name", prospect.name)
    out.setdefault("title", prospect.title)
    return out
