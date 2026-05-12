# Adding a new brand

Six steps to plug a new Champions Group brand (or any client brand) into the personalizer.

## 1. Drop a YAML

Create `backend/data/brands/<slug>.yaml`:

```yaml
slug: <slug>
name: <Brand Name>
tagline: <One-line tagline>
logo_url: /brands/<slug>/logo.svg          # served from frontend/public/

tokens:
  brand_accent: "#XXXXXX"                  # the primary brand color
  brand_accent_soft: "#XXXXXX"             # 10–20% tint for backgrounds
  brand_ink: "#XXXXXX"                     # main text
  brand_muted: "#XXXXXX"                   # secondary text
  brand_rule: "#XXXXXX"                    # dividers / borders
  brand_bg: "#XXXXXX"                      # page background
  font_primary: "Brand Sans"
  font_secondary: "Brand Display"
  font_google_url: "https://fonts.googleapis.com/css2?..."

sender_default:
  company: <Brand Name>
  offer: <One- or two-sentence value prop in the brand's voice>

system_prompt_addendum: |
  Two or three lines describing the brand voice. Substantive only — what to
  call the company (e.g. "intelligence platform" not "data vendor"), what
  numbers to cite, the tone register.

voice_keywords: [comma, separated, list]

default_model: anthropic/claude-sonnet-4.5
```

## 2. Drop the logo (optional)

Place a transparent SVG at `frontend/public/brands/<slug>/logo.svg`. The frontend reads `logo_url` from the brand config and serves it from the frontend's public directory.

## 3. Visit `/lead-magnet/<slug>`

Tokens, copy, and font apply automatically. Zero code change required.

## 4. Verify with the test suite

```bash
cd backend
pytest tests/unit/test_brand_service.py -k <slug>
```

The test asserts that every required hex token is well-formed and `default_model` is non-empty.

## 5. (Optional) Per-brand domain

Point `personalize.<brand>.com` at the same backend. The `resolve_brand` dependency picks up the first segment of the `Host` header and looks it up against `data/brands/`.

## 6. (Optional) Override the LLM

Set `default_model` in the YAML to any OpenRouter-supported model slug — `openai/gpt-4o-mini`, `meta-llama/llama-3.1-70b-instruct`, a fine-tuned model URL, etc. Then run the eval harness to make sure you're ≥80% of the Claude baseline before flipping the default.

---

## Currently configured brands

| Slug | Source skill on disk |
|---|---|
| `lakeb2b` | `/Users/deep/Celsus/Other/Skills/lakeb2b-brand-guidelines/` |
| `ampliz` | `/Users/deep/Celsus/Other/Skills/ampliz-brand-guidelines/` |
| `champions-group` | `/Users/deep/Celsus/.skills/skills/champions-group-brand/` |
| `span-global` | **No skill found.** Placeholder tokens — replace with real SPAN brand assets before launch. |
