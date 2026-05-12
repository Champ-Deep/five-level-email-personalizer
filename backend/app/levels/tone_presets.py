"""Tone-preset library. Users pick a preset; we append a short style-rule
block to the system prompt that biases tone without overriding the brand
voice or the hard anti-slop ruleset.

Inspired by Lavender's "tone profiles" UX, the #1 quality-of-life request
in 2026 reviews of personalization tools.
"""

from __future__ import annotations

TONE_PRESETS: dict[str, str] = {
    "casual": (
        "Tone: casual, conversational, like you'd write to a former coworker. "
        "Contractions OK. One thought per sentence. No corporate stiffness."
    ),
    "formal": (
        "Tone: formal, precise, executive register. Full sentences, no "
        "contractions. Respectful and measured."
    ),
    "founder": (
        "Tone: dry, founder-to-founder. Assume the reader is a builder. "
        "Lead with a specific observation. No hedging, no marketing language. "
        "Sentences are short and load-bearing."
    ),
    "friendly": (
        "Tone: warm, peer-to-peer. Light wit allowed but never at the "
        "prospect's expense. Read like a real person who's done their homework."
    ),
    "concise": (
        "Tone: maximally concise. Body must be 55-75 words. Cut every "
        "qualifier and adverb. Every sentence does work."
    ),
}


def compose_tone_rule(preset_id: str | None) -> str | None:
    """Returns the style-rule block for a preset, or None if unrecognized."""
    if not preset_id:
        return None
    return TONE_PRESETS.get(preset_id.lower())


def available_presets() -> list[dict[str, str]]:
    return [{"id": k, "rule": v} for k, v in TONE_PRESETS.items()]
