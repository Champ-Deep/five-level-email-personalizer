# Tuning the LLM behind the personalizer

The service is LLM-pluggable by design: every call goes through OpenRouter, and the model is selected per request (or per brand via `default_model` in the brand YAML).

## Why an eval harness

The framework says **"80–90% of Claude is good enough."** That's only true if you can measure it. The eval harness exists so you can:

1. Pick a cheaper or fine-tuned candidate (e.g. `openai/gpt-4o-mini`, your fine-tuned LLaMA via OpenRouter).
2. Run it against the same frozen prospect briefs that the Claude baseline runs against.
3. See an aggregate `mean_score / baseline_score` number per level.
4. Promote the candidate to `default_model` only if it's ≥0.80.

## Running an eval

> The eval CLI is scaffolded for v1.1. The pieces are in place — `app.services.eval_service`, `data/eval/golden_briefs.json` (to be added), and a `eval_runs` Postgres table — but the CLI hasn't shipped yet.

When it ships, the workflow will be:

```bash
python -m app.cli eval \
    --candidate openai/gpt-4o-mini \
    --baseline anthropic/claude-opus-4-7 \
    --report runs/eval-2026-05-12.json
```

The judge is Claude scoring 5 axes (relevance-to-anchor, voice match, length compliance, no-buzzword, JSON validity) on 0–10. Aggregate score `mean(candidate) / mean(baseline)` is "% of Claude."

## Swapping the default

Once you have a passing candidate:

```yaml
# backend/data/brands/<slug>.yaml
default_model: openai/gpt-4o-mini-fine-tuned-2026-05
```

Hot-reload of the YAML happens on next request — no redeploy needed.

## Fine-tuning data export (planned)

Each successful production run already stores `(brief, level, sender, brand, email)` tuples that constitute a fine-tuning dataset. v1.1 will add `python -m app.cli export-finetune --brand lakeb2b --format openai-jsonl` so you can fine-tune from real usage.
