"""Pairwise blind judge for email personalization quality.

The judge sees two emails labeled A and B (order randomized so position bias
doesn't leak), scores each on the rubric, and returns structured JSON. We
compute `mean(candidate) / mean(baseline)` to report a "% of Claude" number.

The baseline lives in `data/eval/golden_emails.json` — Chief's output for
each frozen prospect. Add more entries to the file to widen the eval set;
no code change needed.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.levels.schemas import EmailDraft, ProspectInput, SenderInput
from app.services.brand_service import load_brand
from app.services.llm.base import LLMProvider
from app.services.llm.openrouter import extract_json
from app.services.llm.registry import get_provider
from app.services.personalizer import personalize_one


AXES: tuple[str, ...] = (
    "specificity_to_prospect",
    "signal_fusion",
    "voice_naturalness",
    "constraint_compliance",
    "opening_strength",
    "cta_softness",
)


@dataclass
class AxisScore:
    baseline: float
    candidate: float

    @property
    def delta(self) -> float:
        return self.candidate - self.baseline


@dataclass
class CaseResult:
    case_id: str
    axes: dict[str, AxisScore]
    judge_reasoning: str
    candidate_subject: str
    candidate_body: str
    baseline_subject: str
    baseline_body: str

    @property
    def baseline_mean(self) -> float:
        return sum(a.baseline for a in self.axes.values()) / max(len(self.axes), 1)

    @property
    def candidate_mean(self) -> float:
        return sum(a.candidate for a in self.axes.values()) / max(len(self.axes), 1)

    @property
    def percent_of_baseline(self) -> float:
        b = self.baseline_mean
        if b <= 0:
            return 1.0
        return self.candidate_mean / b


@dataclass
class EvalReport:
    results: list[CaseResult]
    judge_model: str
    candidate_model: str

    @property
    def baseline_mean(self) -> float:
        n = len(self.results) or 1
        return sum(r.baseline_mean for r in self.results) / n

    @property
    def candidate_mean(self) -> float:
        n = len(self.results) or 1
        return sum(r.candidate_mean for r in self.results) / n

    @property
    def percent_of_baseline(self) -> float:
        if self.baseline_mean <= 0:
            return 1.0
        return self.candidate_mean / self.baseline_mean

    def per_axis_means(self) -> dict[str, tuple[float, float]]:
        """For each axis: (baseline_mean, candidate_mean)."""
        out: dict[str, tuple[float, float]] = {}
        for axis in AXES:
            baselines = [r.axes[axis].baseline for r in self.results if axis in r.axes]
            cands = [r.axes[axis].candidate for r in self.results if axis in r.axes]
            if baselines and cands:
                out[axis] = (
                    sum(baselines) / len(baselines),
                    sum(cands) / len(cands),
                )
        return out


def _judge_prompt(prospect: dict, sender: dict, email_a: dict, email_b: dict) -> str:
    rubric = "\n".join(f"  - {a}" for a in AXES)
    return f"""You are a senior B2B sales-content editor grading two cold emails written for the same prospect.

PROSPECT:
  name: {prospect['name']}
  title: {prospect['title']}
  domain: {prospect['domain']}

SENDER & OFFER:
  {sender['name']} at {sender['company']}
  offer: {sender['offer']}

You will score two emails labeled A and B on six axes (0-10, integers).

Rubric:
{rubric}

  · specificity_to_prospect (0-10): how concretely the email references real signals about the specific prospect/company — penalize generic claims that could apply to any company in the industry
  · signal_fusion (0-10): how well it weaves industry + company + role + individual + synthesized-POV layers into one coherent argument
  · voice_naturalness (0-10): how human and founder-to-founder the prose reads — penalize AI tells (em-dashes, "not X but Y" constructions, throat-clearing openers, vague abstractions, generic SaaS-speak)
  · constraint_compliance (0-10): no em-dashes/en-dashes, no buzzwords (synergy, leverage, streamline, navigate, robust, holistic, seamless, transformative, paradigm, cutting-edge, etc), no "not X, but Y", no opener clichés (hope this finds you, I noticed that you, quick question), single sign-off, subject ≤ 8 words and no question mark in subject, body 65-120 words
  · opening_strength (0-10): how compelling the first sentence is — does it earn the read with a specific concrete observation, or read like templated outbound
  · cta_softness (0-10): does it end with a soft permission-ask vs. a hard "book a demo / click here"

JUDGING RULES:
1. Be strict. A 10 is "I would forward this to my sales team as an example." A 5 is "acceptable but unremarkable." A 2 is "this would not get a reply."
2. Em-dashes (— and –) are an automatic constraint_compliance penalty of -3 each, capped at 0.
3. "not just X, but Y" or "it's not just X, it's Y" patterns are an automatic -3 on constraint_compliance.
4. Duplicate sign-offs (two "Best, [name]" blocks) are an automatic -2 on constraint_compliance.
5. Generic phrasing that could apply to any company in the industry caps specificity_to_prospect at 5.

EMAIL A:
Subject: {email_a['subject']}

{email_a['body']}

EMAIL B:
Subject: {email_b['subject']}

{email_b['body']}

Return ONLY this JSON (no fences, no preamble):
{{
  "a": {{ "specificity_to_prospect": int, "signal_fusion": int, "voice_naturalness": int, "constraint_compliance": int, "opening_strength": int, "cta_softness": int }},
  "b": {{ "specificity_to_prospect": int, "signal_fusion": int, "voice_naturalness": int, "constraint_compliance": int, "opening_strength": int, "cta_softness": int }},
  "winner": "A" | "B" | "tie",
  "reasoning": "<3-5 sentences explaining the key differences and why the winner won>"
}}"""


async def _judge_pair(
    judge: LLMProvider,
    judge_model: str,
    prospect: dict,
    sender: dict,
    baseline: dict,
    candidate: dict,
) -> tuple[dict[str, AxisScore], str]:
    # Randomize order so position bias doesn't favor either.
    candidate_is_a = random.choice([True, False])
    email_a = candidate if candidate_is_a else baseline
    email_b = baseline if candidate_is_a else candidate

    prompt = _judge_prompt(prospect, sender, email_a, email_b)
    raw = await judge.chat(
        [{"role": "user", "content": prompt}],
        model=judge_model,
        max_tokens=1500,
        temperature=0.0,
        system="You are a senior B2B sales-content editor. Score strictly. Return only valid JSON.",
    )
    data = extract_json(raw)

    a_scores = data["a"]
    b_scores = data["b"]
    cand_scores = a_scores if candidate_is_a else b_scores
    base_scores = b_scores if candidate_is_a else a_scores

    axes: dict[str, AxisScore] = {}
    for axis in AXES:
        axes[axis] = AxisScore(
            baseline=float(base_scores.get(axis, 0)),
            candidate=float(cand_scores.get(axis, 0)),
        )
    return axes, data.get("reasoning", "")


def load_golden(path: Optional[Path] = None) -> list[dict[str, Any]]:
    p = path or Path(__file__).resolve().parents[2] / "data" / "eval" / "golden_emails.json"
    return json.loads(p.read_text())["cases"]


async def run_eval(
    *,
    candidate_model: Optional[str] = None,
    judge_model: Optional[str] = None,
    brand_slug: str = "lakeb2b",
    golden_path: Optional[Path] = None,
) -> EvalReport:
    settings = get_settings()
    judge_model = judge_model or "anthropic/claude-opus-4.1"
    candidate_model = candidate_model or settings.openrouter_default_model

    provider = get_provider("openrouter")
    brand = load_brand(brand_slug)
    cases = load_golden(golden_path)

    results: list[CaseResult] = []
    for case in cases:
        prospect_in = ProspectInput(**case["prospect"])
        sender_in = SenderInput(**case["sender"])
        baseline = case["baseline"]

        # Generate our candidate using the same prospect+sender.
        response = await personalize_one(
            prospect_in,
            brand,
            provider,
            sender=sender_in,
            levels=[5],
            model=candidate_model,
        )
        cand_email = response.emails[5]
        candidate_payload = {
            "subject": cand_email.subject,
            "body": _append_signoff(cand_email.body, sender_in.name),
        }
        baseline_payload = {
            "subject": baseline["subject"],
            "body": baseline["body"],
        }

        axes, reasoning = await _judge_pair(
            provider, judge_model, case["prospect"], case["sender"], baseline_payload, candidate_payload
        )
        results.append(CaseResult(
            case_id=case["id"],
            axes=axes,
            judge_reasoning=reasoning,
            candidate_subject=cand_email.subject,
            candidate_body=candidate_payload["body"],
            baseline_subject=baseline["subject"],
            baseline_body=baseline["body"],
        ))

    return EvalReport(results=results, judge_model=judge_model, candidate_model=candidate_model)


def _append_signoff(body: str, sender_name: str) -> str:
    cleaned = body.rstrip()
    # Strip any trailing sign-off the LLM may have included.
    import re as _re
    cleaned = _re.sub(r"\s*Best,\s*[^\n]*\s*$", "", cleaned, flags=_re.IGNORECASE).rstrip()
    return f"{cleaned}\n\nBest,\n{sender_name}"
