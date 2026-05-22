"""Inbound reply triage: classify intent + suggest response drafts.

Designed for the post-send loop: a rep pastes the inbound reply, gets a
fast classification (intent + suggested next action), and optionally
asks for 2-3 draft response options.

`classify-bulk` extends this to the "I just came back from PTO and have
20 replies sitting in the inbox" workflow — paste them all, get a
grouped summary, draft a single template per intent.

All endpoints are deliberately stateless — they take the reply text
inline and return JSON. No persistence here (reply storage / inbox
sync is a bigger feature, queued).
"""

from __future__ import annotations

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import TokenSubject, require_user
from app.core.config import get_settings
from app.services.llm.openrouter import extract_json
from app.services.llm.registry import get_provider

router = APIRouter(prefix="/replies", tags=["replies"])


ReplyIntent = Literal[
    "interested",
    "not_interested",
    "ooo",
    "wrong_person",
    "unsubscribe",
    "info_request",
    "scheduling",
    "other",
]


class ClassifyIn(BaseModel):
    reply_body: str = Field(..., min_length=3, max_length=10000)
    original_email: Optional[str] = Field(None, max_length=4000)
    sender_first_name: Optional[str] = None
    model: Optional[str] = None


class ClassifyOut(BaseModel):
    intent: ReplyIntent
    confidence: int  # 0-100
    summary: str
    suggested_action: str


CLASSIFY_PROMPT = """You triage inbound replies to cold outbound emails.

Classify the reply into ONE intent:
  interested       — they want a call/demo/more info, positive engagement
  not_interested   — explicit decline, "no thanks", "remove me"
  ooo              — auto-reply (out of office, on leave, on vacation)
  wrong_person     — "I don't handle this", "try [other person]", forwarded
  unsubscribe      — explicit unsubscribe request (LEGAL: must honor)
  info_request     — asking for pricing, materials, more detail
  scheduling       — proposing/accepting a meeting time
  other            — anything that doesn't fit above

Return ONLY this JSON (no fences, no preamble):
{{
  "intent": "<one of the labels above>",
  "confidence": <integer 0-100>,
  "summary": "<one short sentence describing what the reply says>",
  "suggested_action": "<one short sentence telling the rep what to do next>"
}}

REPLY BODY:
{reply_body}

ORIGINAL EMAIL (for context, may be empty):
{original_email}
"""


@router.post("/classify", response_model=ClassifyOut)
async def classify_reply(
    body: ClassifyIn,
    subj: TokenSubject = Depends(require_user),
) -> ClassifyOut:
    prompt = CLASSIFY_PROMPT.format(
        reply_body=body.reply_body.strip(),
        original_email=(body.original_email or "").strip(),
    )
    provider = get_provider("openrouter")
    try:
        raw = await provider.chat(
            [{"role": "user", "content": prompt}],
            model=body.model or "meta-llama/llama-4-maverick",
            max_tokens=400,
            temperature=0.1,
            system="You are a precise B2B sales-ops assistant. Return ONLY valid JSON.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Classifier failed: {e}") from e
    data = extract_json(raw)
    return ClassifyOut(
        intent=data.get("intent", "other"),
        confidence=int(data.get("confidence", 0)),
        summary=str(data.get("summary", "")).strip(),
        suggested_action=str(data.get("suggested_action", "")).strip(),
    )


class DraftIn(BaseModel):
    reply_body: str = Field(..., min_length=3, max_length=10000)
    intent: ReplyIntent
    original_email: Optional[str] = Field(None, max_length=4000)
    sender_name: str = Field(..., max_length=200)
    sender_company: str = Field(..., max_length=200)
    sender_offer: Optional[str] = Field(None, max_length=600)
    model: Optional[str] = None
    n: int = Field(2, ge=1, le=3, description="Number of draft options to generate")


class DraftOption(BaseModel):
    label: str
    subject: str | None
    body: str


class DraftOut(BaseModel):
    drafts: list[DraftOption]


class BulkReplyItem(BaseModel):
    """One reply in a bulk-classify request. `id` lets the caller stitch
    results back to its own list (sales reps usually paste replies with
    sender names attached and want to know which one matched which)."""
    id: str = Field(..., min_length=1, max_length=80)
    reply_body: str = Field(..., min_length=3, max_length=10000)
    original_email: Optional[str] = Field(None, max_length=4000)


class BulkClassifyIn(BaseModel):
    items: list[BulkReplyItem] = Field(..., min_length=1, max_length=50)
    model: Optional[str] = None


class BulkClassifyItem(BaseModel):
    id: str
    intent: ReplyIntent
    confidence: int
    summary: str
    suggested_action: str


class BulkClassifyOut(BaseModel):
    items: list[BulkClassifyItem]
    by_intent: dict[str, list[str]]  # intent -> list of item ids


@router.post("/classify-bulk", response_model=BulkClassifyOut)
async def classify_replies_bulk(
    body: BulkClassifyIn,
    subj: TokenSubject = Depends(require_user),
) -> BulkClassifyOut:
    """Fan out the single-reply classifier across N items in parallel.

    Cap is 50 items per request — that's plenty for the "back from PTO"
    workflow and keeps token cost predictable. The semaphore matches
    the personalizer's so we don't double up against the OpenRouter
    rate limit during a busy minute.
    """
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.max_concurrent_levels)
    provider = get_provider("openrouter")
    model = body.model or "meta-llama/llama-4-maverick"

    async def _classify(item: BulkReplyItem) -> BulkClassifyItem:
        prompt = CLASSIFY_PROMPT.format(
            reply_body=item.reply_body.strip(),
            original_email=(item.original_email or "").strip(),
        )
        try:
            async with semaphore:
                raw = await provider.chat(
                    [{"role": "user", "content": prompt}],
                    model=model,
                    max_tokens=400,
                    temperature=0.1,
                    system="You are a precise B2B sales-ops assistant. Return ONLY valid JSON.",
                )
            data = extract_json(raw)
            return BulkClassifyItem(
                id=item.id,
                intent=data.get("intent", "other"),
                confidence=int(data.get("confidence", 0)),
                summary=str(data.get("summary", "")).strip(),
                suggested_action=str(data.get("suggested_action", "")).strip(),
            )
        except Exception as e:
            # One failed reply doesn't tank the batch — surface the
            # error in `summary` so the rep can see what went wrong on
            # that row. Intent falls back to "other" so the row still
            # groups somewhere.
            return BulkClassifyItem(
                id=item.id,
                intent="other",
                confidence=0,
                summary=f"Classification failed: {e}",
                suggested_action="Review manually.",
            )

    results = await asyncio.gather(*[_classify(it) for it in body.items])
    by_intent: dict[str, list[str]] = {}
    for r in results:
        by_intent.setdefault(r.intent, []).append(r.id)
    return BulkClassifyOut(items=results, by_intent=by_intent)


DRAFT_PROMPT = """You draft response options to inbound replies on a cold-email thread.

Reply intent: {intent}
Generate {n} distinct response drafts that match the intent. Each should:

  - Sound like a real human at {sender_company}, not a template
  - Be 40-90 words, plain prose, single soft CTA
  - For "interested" / "info_request" / "scheduling": offer a concrete next step
  - For "not_interested" / "unsubscribe": acknowledge, close gracefully, NO follow-up
  - For "ooo": acknowledge and propose a date after they return
  - For "wrong_person": ask for the right person politely, ONE question only

Hard rules:
  - No em-dashes or en-dashes
  - No "not X, but Y" constructions
  - No buzzwords (delve, leverage, streamline, navigate, robust, holistic, seamless, transformative, paradigm, cutting-edge)
  - First name greeting only
  - Sign off: Best,\\n{sender_name}

Return ONLY this JSON (no fences):
{{
  "drafts": [
    {{ "label": "<short label e.g. 'Direct ask'>", "subject": "<optional reply subject or null>", "body": "<plain prose>" }}
  ]
}}

SENDER OFFER (if mentioning the original ask):
{sender_offer}

ORIGINAL EMAIL:
{original_email}

REPLY BODY:
{reply_body}
"""


@router.post("/draft", response_model=DraftOut)
async def draft_replies(
    body: DraftIn,
    subj: TokenSubject = Depends(require_user),
) -> DraftOut:
    prompt = DRAFT_PROMPT.format(
        intent=body.intent,
        n=body.n,
        sender_company=body.sender_company,
        sender_name=body.sender_name,
        sender_offer=body.sender_offer or "(not provided)",
        original_email=(body.original_email or "(not provided)").strip(),
        reply_body=body.reply_body.strip(),
    )
    provider = get_provider("openrouter")
    try:
        raw = await provider.chat(
            [{"role": "user", "content": prompt}],
            model=body.model or "deepseek/deepseek-v4-pro",
            max_tokens=2000,
            temperature=0.6,
            system="You are an elite B2B sales rep drafting reply options. Return ONLY valid JSON.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Drafter failed: {e}") from e
    data = extract_json(raw)
    drafts_raw = data.get("drafts") or []
    drafts = [
        DraftOption(
            label=str(d.get("label", "Option")).strip(),
            subject=d.get("subject") if d.get("subject") not in (None, "null", "") else None,
            body=str(d.get("body", "")).strip(),
        )
        for d in drafts_raw
        if d.get("body")
    ]
    return DraftOut(drafts=drafts[:body.n])
