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
    LinkedInDraft,
    PersonalizeRequest,
    PersonalizeResponse,
    ProspectInput,
    SenderInput,
    Variation,
    VariationSpec,
)
from app.services.brand_service import BrandConfig
from app.services.llm.base import LLMError, LLMProvider
from app.services.llm.openrouter import extract_json
from app.levels.followup_prompts import followup_prompt, sequence_step_prompt
from app.levels.linkedin_prompts import linkedin_prompt
from app.services.research_service import research_prospect
from app.services.scores import score_email


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
        "charCount": "char_count",
    }
    return {aliases.get(k, k): v for k, v in data.items()}


def _validate_linkedin(draft: LinkedInDraft) -> list[str]:
    """Anti-slop pass for LinkedIn DMs. Mirrors `_validate` for emails
    but with different rules:
      - HARD 300-char limit
      - same banned words + em-dash + not-X-but-Y check
    The 300-char check uses len(body), not word count, because LinkedIn
    truncates by character.
    """
    warnings: list[str] = []
    body = (draft.body or "").strip()
    draft.char_count = len(body)
    if draft.char_count == 0:
        warnings.append("linkedin body is empty")
    elif draft.char_count > 300:
        warnings.append(f"linkedin body is {draft.char_count} chars (max 300)")

    lower = body.lower()
    for word in BANNED_WORDS:
        if word in lower:
            warnings.append(f"contains banned phrase: '{word}'")
    for dash in EM_DASH_CHARS:
        if dash in body:
            warnings.append(f"contains em/en-dash '{dash}' (use commas or periods)")
            break
    for pattern in NOT_X_BUT_Y_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            warnings.append(f"contains AI cliché 'not X, but Y': '{m.group(0).strip()}'")
            break
    return warnings


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
            max_tokens=6000,
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
                max_tokens=6000,
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


def _resolve_variations(request: PersonalizeRequest, brand: BrandConfig) -> list[VariationSpec]:
    if request.variations:
        return list(request.variations)
    # Legacy single-model path: respect request.model > brand.default_model.
    if request.model:
        return [VariationSpec(slot="A", model=request.model, label=request.model)]
    settings = get_settings()
    return [VariationSpec(**spec) for spec in settings.default_variation_specs]


async def personalize(
    request: PersonalizeRequest,
    brand: BrandConfig,
    provider: LLMProvider,
) -> PersonalizeResponse:
    settings = get_settings()

    sender = request.sender or SenderInput(
        name=brand.sender_default.name or brand.name,
        company=brand.sender_default.company,
        offer=brand.sender_default.offer,
    )

    brief = await research_prospect(request.prospect, provider, brand_addendum=brand.system_prompt_addendum)

    # Determine which level to generate per variation. The fused 5-layer email
    # is level 5; we keep `levels` in the schema for backwards compat but for
    # the variation pipeline we always run level 5 and replicate it per slot.
    primary_level = max(request.levels) if request.levels else 5
    specs = _resolve_variations(request, brand)

    # Compose tone preset (if any) into the style_rules channel — both
    # caller-supplied rules and the tone preset are appended to the system
    # prompt; neither replaces the brand voice or the hard anti-slop block.
    from app.levels.tone_presets import compose_tone_rule

    tone_rule = compose_tone_rule(request.tone_preset)
    composed_style_rules = "\n\n".join(filter(None, [tone_rule, request.style_rules])) or None

    semaphore = asyncio.Semaphore(settings.max_concurrent_levels)
    tasks = [
        _generate_one(
            level=primary_level,
            brief=brief,
            sender=sender,
            prospect_title=request.prospect.title,
            provider=provider,
            model=spec.model,
            brand=brand,
            system_override=request.system_prompt_override,
            style_rules=composed_style_rules,
            semaphore=semaphore,
        )
        for spec in specs
    ]
    drafts = await asyncio.gather(*tasks, return_exceptions=True)

    variations: list[Variation] = []
    for spec, result in zip(specs, drafts):
        if isinstance(result, EmailDraft):
            draft = result
        else:
            draft = EmailDraft(
                subject=f"[Variation {spec.slot} ({spec.model}) failed]",
                body=str(result),
                word_count=0,
                anchor_signal="",
                warnings=[f"generation_error: {type(result).__name__}"],
            )
        # Attach deliverability + reply-likelihood scores to every variation.
        if not draft.subject.startswith("["):
            draft.scores = score_email(draft, brief)
        variations.append(Variation(slot=spec.slot, label=spec.label or spec.model, model=spec.model, email=draft))

    # Resolve effective sequence length. `include_followup=true` from
    # older callers is honored as sequence_length>=2 so nothing breaks.
    effective_sequence_length = max(
        request.sequence_length,
        2 if request.include_followup else 1,
    )

    # Generate follow-up steps 2..N. Across variations we fan out in
    # parallel; *within* a variation each step needs the previous one's
    # content (different-angle prompting), so the steps run sequentially
    # per variation.
    if effective_sequence_length >= 2 and variations:
        async def _gen_step(
            v: Variation, step: int, prior_emails: list[EmailDraft]
        ) -> EmailDraft:
            prompt = sequence_step_prompt(
                step=step, brief=brief, sender=sender, prior_emails=prior_emails
            )
            try:
                async with semaphore:
                    raw = await provider.chat(
                        [{"role": "user", "content": prompt}],
                        model=v.model,
                        max_tokens=6000,
                        temperature=0.7,
                        system=system_prompt(brand.system_prompt_addendum, composed_style_rules),
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
                draft.scores = score_email(draft, brief)
                return draft
            except Exception as e:
                return EmailDraft(
                    subject=f"[Step {step} ({v.slot}) failed]",
                    body=str(e), word_count=0, anchor_signal="",
                    warnings=[f"sequence_step_{step}_error: {type(e).__name__}"],
                )

        async def _gen_chain(v: Variation) -> tuple[str, list[EmailDraft]]:
            if v.email.subject.startswith("[") or not v.email.body:
                return v.slot, []
            chain: list[EmailDraft] = []
            prior = [v.email]
            for step in range(2, effective_sequence_length + 1):
                draft = await _gen_step(v, step, prior)
                chain.append(draft)
                # Only feed *successful* drafts into the next step's
                # context — a "[Step N failed]" placeholder shouldn't
                # confuse the model writing step N+1.
                if not draft.subject.startswith("["):
                    prior = prior + [draft]
            return v.slot, chain

        chains = await asyncio.gather(*[_gen_chain(v) for v in variations], return_exceptions=False)
        chain_by_slot = {slot: chain for slot, chain in chains}
        for v in variations:
            v.sequence = chain_by_slot.get(v.slot, [])

    # Optional LinkedIn DM: same model as the variation. Runs in
    # parallel across variations under the same semaphore so we don't
    # blow the OpenRouter rate limit on a single big batch.
    if request.include_linkedin and variations:
        async def _gen_linkedin(v: Variation) -> tuple[str, LinkedInDraft | None]:
            if v.email.subject.startswith("[") or not v.email.body:
                return v.slot, None
            prompt = linkedin_prompt(brief, sender, v.email)
            try:
                async with semaphore:
                    raw = await provider.chat(
                        [{"role": "user", "content": prompt}],
                        model=v.model,
                        max_tokens=1500,
                        temperature=0.7,
                        system=system_prompt(brand.system_prompt_addendum, composed_style_rules),
                    )
                data = _normalize_email_keys(extract_json(raw))
                draft = LinkedInDraft(
                    body=str(data.get("body", "")).strip(),
                    char_count=int(data.get("char_count") or len(str(data.get("body", "")))),
                    anchor_signal=str(data.get("anchor_signal", "")).strip(),
                )
                w = _validate_linkedin(draft)
                if w:
                    draft.warnings = w
                return v.slot, draft
            except Exception as e:
                return v.slot, LinkedInDraft(
                    body=f"[LinkedIn DM {v.slot} failed: {e}]",
                    char_count=0, anchor_signal="",
                    warnings=[f"linkedin_error: {type(e).__name__}"],
                )

        linkedins = await asyncio.gather(*[_gen_linkedin(v) for v in variations], return_exceptions=False)
        linkedin_by_slot = {slot: draft for slot, draft in linkedins}
        for v in variations:
            v.linkedin = linkedin_by_slot.get(v.slot)

    # Back-compat: surface variation A under `emails[level]` for single-model callers.
    emails: dict[int, EmailDraft] = {}
    if variations:
        emails[primary_level] = variations[0].email

    # ICP fit (optional, opportunistic). Uses an ad-hoc description if provided;
    # the API layer resolves profile_id → description before calling personalize().
    icp_fit = None
    icp_desc = getattr(request, "icp_description", None)
    if icp_desc:
        try:
            from app.services.icp_scorer import score_icp_fit
            r = await score_icp_fit(
                request.prospect, icp_desc, provider,
                model="meta-llama/llama-4-maverick", brief=brief,
            )
            from app.levels.schemas import IcpFit
            icp_fit = IcpFit(score=r["score"], reason=r["reason"], profile_id=getattr(request, "icp_profile_id", None))
        except Exception as e:
            import logging
            logging.warning("ICP scoring failed: %s", e)

    return PersonalizeResponse(brand=brand.slug, brief=brief, variations=variations, icp_fit=icp_fit, emails=emails)


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
    tone_preset: Optional[str] = None,
    include_followup: bool = False,
    sequence_length: int = 1,
    include_linkedin: bool = False,
    variations: Optional[list] = None,
) -> PersonalizeResponse:
    """Convenience entrypoint for SDK / worker callers."""
    request = PersonalizeRequest(
        prospect=prospect,
        sender=sender,
        levels=levels or [5],
        provider=provider.name,
        model=model,
        system_prompt_override=system_prompt_override,
        style_rules=style_rules,
        tone_preset=tone_preset,
        include_followup=include_followup,
        sequence_length=sequence_length,
        include_linkedin=include_linkedin,
        variations=variations,
    )
    return await personalize(request, brand, provider)
