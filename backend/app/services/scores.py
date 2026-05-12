"""Two heuristic scores attached to every generated email.

These are NOT ML models — they're deterministic, fast, explainable rules
that surface immediately in the API response and UI. They give the user a
"why this score" breakdown so they can make informed send decisions, which
is the #1 complaint in 2026 reviews of Lavender / Instantly / Lemlist:
"the AI writes but never tells me if it'll land."

Two scores, each 0-100:

- DeliverabilityScore: spam-filter friendliness (subject, body, structure)
- ReplyLikelihoodScore: how reply-worthy the email reads (specificity,
  CTA softness, length, opening strength)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.levels.schemas import Brief, EmailDraft


SPAM_TRIGGER_WORDS: tuple[str, ...] = (
    "free", "guarantee", "guaranteed", "urgent", "act now", "limited time",
    "click here", "100%", "no risk", "winner", "congratulations",
    "this isn't spam", "make money fast", "double your", "exclusive deal",
    "buy now", "click below", "viagra", "cash bonus", "for free",
    "save up to", "satisfaction guaranteed", "no obligation",
)


@dataclass
class ScoreDetail:
    score: int                # 0-100
    factors: dict[str, str]   # label → "+12" / "-8" with reason


def _count(haystack: str, needles: tuple[str, ...]) -> list[str]:
    h = haystack.lower()
    return [n for n in needles if n in h]


def _has_specifics(body: str, brief: Brief | None) -> int:
    """Returns count of brief signals that actually appear in the body."""
    if brief is None:
        return 0
    needles: list[str] = []
    needles.extend(brief.company_signals or [])
    needles.extend(brief.individual_signals or [])
    needles.extend(brief.industry_trends or [])
    needles.extend(brief.role_pain_points or [])
    if brief.company:
        needles.append(brief.company)
    if brief.industry:
        needles.append(brief.industry)
    body_low = body.lower()
    return sum(1 for n in needles if n and len(n) > 6 and n.lower()[:30] in body_low)


def deliverability_score(draft: EmailDraft) -> ScoreDetail:
    """Spam-filter friendliness. Starts at 100, deducts for risk factors."""
    subject = draft.subject or ""
    body = draft.body or ""
    score = 100
    factors: dict[str, str] = {}

    spam_hits = _count(subject + "\n" + body, SPAM_TRIGGER_WORDS)
    if spam_hits:
        delta = -10 * len(spam_hits)
        score += delta
        factors["spam_triggers"] = f"{delta} ({', '.join(spam_hits[:3])})"

    # ALL-CAPS words in subject (single-word abbreviations OK).
    caps_words = [w for w in subject.split() if len(w) >= 4 and w.isupper()]
    if caps_words:
        delta = -8 * len(caps_words)
        score += delta
        factors["all_caps_subject"] = f"{delta} ({len(caps_words)} word(s))"

    # Excessive punctuation: !! or ???
    if re.search(r"(!!|\?\?|\.\.\.\.+)", subject + body):
        score -= 8
        factors["punctuation"] = "-8 (excessive ! or ?)"

    # $ count (currency mentions trigger filters)
    dollar_count = (subject + body).count("$")
    if dollar_count >= 2:
        score -= 5 * (dollar_count - 1)
        factors["currency_mentions"] = f"-{5 * (dollar_count - 1)} ({dollar_count} '$' signs)"

    # Link count (cold email best practice: 0 links)
    link_count = len(re.findall(r"https?://\S+", body))
    if link_count > 0:
        score -= 10 * link_count
        factors["links"] = f"-{10 * link_count} ({link_count} link(s) — cold emails should have zero)"

    # Subject length sweet spot is 4-7 words
    sw = len(subject.split())
    if sw == 0:
        score -= 20
        factors["subject_empty"] = "-20 (missing subject)"
    elif sw > 8:
        score -= 6
        factors["subject_too_long"] = f"-6 ({sw} words; aim for 4-7)"
    elif sw < 3:
        score -= 4
        factors["subject_too_short"] = f"-4 ({sw} words)"

    # Question marks in subject (filters dislike them in cold mail)
    if "?" in subject:
        score -= 4
        factors["question_in_subject"] = "-4 (subjects with '?' get worse open rates)"

    # Body length compliance
    word_count = draft.word_count or len(re.findall(r"\b[\w'-]+\b", body))
    if word_count < 50:
        score -= 8
        factors["body_too_short"] = f"-8 ({word_count} words; min 65)"
    elif word_count > 160:
        score -= 10
        factors["body_too_long"] = f"-10 ({word_count} words; aim 65-120)"

    score = max(0, min(100, score))
    return ScoreDetail(score=score, factors=factors)


def reply_likelihood_score(draft: EmailDraft, brief: Brief | None = None) -> ScoreDetail:
    """Heuristic "would a busy human reply?" score. Starts at 50, adjusts."""
    subject = draft.subject or ""
    body = draft.body or ""
    score = 50
    factors: dict[str, str] = {}

    # Specificity bonus: count actual brief signals that appear in the body.
    specifics = _has_specifics(body, brief) if brief else 0
    if specifics > 0:
        bonus = min(25, specifics * 5)
        score += bonus
        factors["specifics"] = f"+{bonus} ({specifics} concrete signal(s) referenced)"
    else:
        score -= 10
        factors["no_specifics"] = "-10 (no brief signals referenced — reads generic)"

    # Soft permission-ask CTA boost.
    body_low = body.lower()
    if re.search(r"worth a (?:quick )?look\??", body_low) or re.search(r"open to (?:a |an )?(?:quick )?(?:chat|call|word)", body_low):
        score += 12
        factors["soft_cta"] = "+12 (soft permission-ask CTA)"
    elif re.search(r"book (?:a )?(?:demo|meeting|call)", body_low) or "schedule a call" in body_low:
        score -= 8
        factors["hard_cta"] = "-8 (hard 'book a demo' CTA — feels sales-y)"

    # Length sweet spot 65-110.
    word_count = draft.word_count or len(re.findall(r"\b[\w'-]+\b", body))
    if 65 <= word_count <= 110:
        score += 8
        factors["length"] = f"+8 ({word_count} words — ideal range)"
    elif word_count > 130:
        score -= 8
        factors["length"] = f"-8 ({word_count} words — too long)"

    # Opening: starts with prospect's name vs generic greeting
    first_line = next((ln for ln in body.split("\n") if ln.strip()), "")
    if brief and brief.name and first_line.lower().startswith(brief.name.split()[0].lower()):
        score += 5
        factors["personal_open"] = "+5 (opens with prospect's first name)"

    # First sentence specificity: does it contain a number, date, or company-specific noun?
    first_sentence = re.split(r"[.!?]", body, maxsplit=1)[0]
    if re.search(r"\b\d", first_sentence):
        score += 5
        factors["concrete_opener"] = "+5 (opener contains a number — concrete)"

    # Buzzwords / AI tells suppress score.
    ai_tells = ("delve", "leverage", "navigate", "robust", "holistic", "seamless",
                "transformative", "paradigm", "cutting-edge", "best-in-class")
    hits = _count(body, ai_tells)
    if hits:
        score -= 6 * len(hits)
        factors["ai_tells"] = f"-{6 * len(hits)} ({', '.join(hits[:3])})"

    # Em-dash auto-penalty
    if "—" in body or "–" in body:
        score -= 5
        factors["em_dash"] = "-5 (em-dash present — AI tell)"

    score = max(0, min(100, score))
    return ScoreDetail(score=score, factors=factors)


def score_email(draft: EmailDraft, brief: Brief | None = None) -> dict:
    d = deliverability_score(draft)
    r = reply_likelihood_score(draft, brief)
    return {
        "deliverability": {"score": d.score, "factors": d.factors},
        "reply_likelihood": {"score": r.score, "factors": r.factors},
    }
