from __future__ import annotations

import asyncio
import re
from typing import Optional

from app.core.config import get_settings
from app.levels.prompts import (
    BANNED_WORDS,
    EM_DASH_CHARS,
    NOT_X_BUT_Y_PATTERNS,
    email_prompt,
    system_prompt,
)
from app.levels.schemas import (
    Brief,
    EmailDraft,
    PersonalizeRequest,
    PersonalizeResponse,
    ProspectInput,
    SenderInput,
)
from app.services.brand_service import BrandConfig
from app.services.llm.base import LLMError, LLMProvider
from app.services.llm.openrouter import extract_json
from app.services.research_service import research_prospect


WORD_RE = re.compile(r"\b[\w'-]+\b")


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def _validate(draft: EmailDraft) -> list[str]:
    warnings: list[str] = []
    subject_words = _count_words(draft.subject)
    if subject_words > 8:
        warnings.append(f"subject is {subject_words} words (max 8)")
    if "?" in draft.subject:
        warnings.append("subject contains a question mark")
    if any(seq.isupper() and len(seq) >= 4 for seq in draft.subject.split()):
        warnings.append("subject contains ALL-CAPS sequence")

    body_words = _count_words(draft.body)
    draft.word_count = body_words
    if body_words < 65:
        warnings.append(f"body is {body_words} words (min 65)")
    elif body_words > 120:
        warnings.append(f"body is {body_words} words (max 120)")

    full = draft.subject + "\n" + draft.body
    lower = full.lower()

    for word in BANNED_WORDS:
        if word in lower:
            warnings.append(f"contains banned phrase: '{word}'")

    for dash in EM_DASH_CHARS:
        if dash in full:
            warnings.append(f"contains em/en-dash '{dash}' (use commas or periods)")
            break

    for pattern in NOT_X_BUT_Y_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            warnings.append(f"contains AI cliché 'not X, but Y': '{m.group(0).strip()}'")
            break

    return warnings


def _normalize_email_keys(data: dict) -> dict:
    aliases = {
        "wordCount": "word_count",
        "anchorSignal": "anchor_signal",
    }
    return {aliases.get(k, k): v for k, v in data.items()}


async def _generate_one(
    *,
    level: int,
    brief: Brief,
    sender: SenderInput,
    prospect_title: str,
    provider: LLMProvider,
    model: str,
    brand: BrandConfig,
    system_override: Optional[str],
    style_rules: Optional[str],
    semaphore: asyncio.Semaphore,
) -> EmailDraft:
    prompt = email_prompt(level, brief, sender, prospect_title)
    brand_addendum = system_override if system_override is not None else brand.system_prompt_addendum
    composed_system = system_prompt(brand_addendum, style_rules)
    async with semaphore:
        raw = await provider.chat(
            [{"role": "user", "content": prompt}],
            model=model,
            max_tokens=900,
            temperature=0.7,
            system=composed_system,
        )
    data = _normalize_email_keys(extract_json(raw))
    draft = EmailDraft(
        subject=str(data.get("subject", "")).strip(),
        body=str(data.get("body", "")).strip(),
        word_count=int(data.get("word_count") or _count_words(data.get("body", ""))),
        anchor_signal=str(data.get("anchor_signal", "")).strip(),
    )
    warnings = _validate(draft)
    if warnings:
        draft.warnings = warnings
        retry = await _retry_strict(
            prompt, warnings, provider, model, composed_system, semaphore
        )
        if retry is not None:
            return retry
    return draft


async def _retry_strict(
    original_prompt: str,
    warnings: list[str],
    provider: LLMProvider,
    model: str,
    composed_system: str,
    semaphore: asyncio.Semaphore,
) -> Optional[EmailDraft]:
    correction = (
        "Your previous draft failed these checks: "
        + "; ".join(warnings)
        + ". Rewrite the email fixing every issue, returning ONLY the same JSON shape."
    )
    async with semaphore:
        try:
            raw = await provider.chat(
                [
                    {"role": "user", "content": original_prompt},
                    {"role": "user", "content": correction},
                ],
                model=model,
                max_tokens=900,
                temperature=0.4,
                system=composed_system,
            )
        except LLMError:
            return None
    try:
        data = _normalize_email_keys(extract_json(raw))
    except LLMError:
        return None
    draft = EmailDraft(
        subject=str(data.get("subject", "")).strip(),
        body=str(data.get("body", "")).strip(),
        word_count=int(data.get("word_count") or _count_words(data.get("body", ""))),
        anchor_signal=str(data.get("anchor_signal", "")).strip(),
    )
    fresh = _validate(draft)
    if fresh:
        draft.warnings = fresh
    return draft


async def personalize(
    request: PersonalizeRequest,
    brand: BrandConfig,
    provider: LLMProvider,
) -> PersonalizeResponse:
    settings = get_settings()
    model = request.model or brand.default_model

    sender = request.sender or SenderInput(
        name=brand.sender_default.name or brand.name,
        company=brand.sender_default.company,
        offer=brand.sender_default.offer,
    )

    brief = await research_prospect(request.prospect, provider, brand_addendum=brand.system_prompt_addendum)

    semaphore = asyncio.Semaphore(settings.max_concurrent_levels)
    tasks = [
        _generate_one(
            level=lvl,
            brief=brief,
            sender=sender,
            prospect_title=request.prospect.title,
            provider=provider,
            model=model,
            brand=brand,
            system_override=request.system_prompt_override,
            style_rules=request.style_rules,
            semaphore=semaphore,
        )
        for lvl in request.levels
    ]
    drafts = await asyncio.gather(*tasks, return_exceptions=True)

    emails: dict[int, EmailDraft] = {}
    for lvl, result in zip(request.levels, drafts):
        if isinstance(result, EmailDraft):
            emails[lvl] = result
        else:
            emails[lvl] = EmailDraft(
                subject=f"[Level {lvl} generation failed]",
                body=str(result),
                word_count=0,
                anchor_signal="",
                warnings=[f"generation_error: {type(result).__name__}"],
            )

    return PersonalizeResponse(brand=brand.slug, brief=brief, emails=emails)


async def personalize_one(
    prospect: ProspectInput,
    brand: BrandConfig,
    provider: LLMProvider,
    *,
    sender: Optional[SenderInput] = None,
    levels: Optional[list[int]] = None,
    model: Optional[str] = None,
    system_prompt_override: Optional[str] = None,
    style_rules: Optional[str] = None,
) -> PersonalizeResponse:
    """Convenience entrypoint for SDK / worker callers."""
    request = PersonalizeRequest(
        prospect=prospect,
        sender=sender,
        levels=levels or [1, 2, 3, 4, 5],
        provider=provider.name,
        model=model,
        system_prompt_override=system_prompt_override,
        style_rules=style_rules,
    )
    return await personalize(request, brand, provider)
