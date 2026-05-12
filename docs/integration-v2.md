# v2 integration recipes

How the standalone service plugs into ChampMail and ChampIQ. Not built in v1 — the architecture is wired so each is a one-day change.

## ChampMail · STEP_PERSONALIZE swap

ChampMail's `CampaignPipeline` (see `/Users/deep/Apps&Projects/ChampMail/backend/app/services/campaign_pipeline.py`) already has a `STEP_PERSONALIZE` stage that currently calls into `pitch_service` from `app/services/ai/openrouter_service.py`.

The swap, inside `CampaignPipeline._personalize_emails`:

```python
from champ_personalize.local import LocalPersonalizer

async def _personalize_emails(self, campaign, prospects):
    personalizer = LocalPersonalizer(brand=campaign.brand_slug)
    out = []
    for prospect, brief in zip(prospects, briefs):
        result = await personalizer.run(
            prospect.model_dump(),
            sender={"name": campaign.sender_name, "company": campaign.brand_slug, "offer": campaign.value_prop},
            levels=[campaign.target_level],  # campaign chooses which level
            model=campaign.model_override,
        )
        out.append(result.emails[campaign.target_level])
    return out
```

Because `LocalPersonalizer` imports backend services directly, there's no HTTP overhead inside the worker. The result shape matches what `CampaignPipeline` already passes downstream to the HTML/send steps.

**Install in ChampMail:**

```bash
# inside ChampMail repo, with our backend on the same Python path
pip install -e "/Users/deep/Apps&Projects/Email Personalization tool/sdk[local]"
```

Or run the personalizer as a separate service and swap `LocalPersonalizer` for `PersonalizerClient(base_url=...)`.

## ChampIQ · Bullpen bulk action

ChampIQ's Bullpen lives at `/Users/deep/Apps&Projects/ChampIQ/champiq-canvas/apps/web/src/components/hub/BullpenPanel.tsx`. It already tracks `selected: Set<number>` of prospects.

Add a button:

```tsx
<button
  onClick={async () => {
    const ids = Array.from(selected);
    const prospects = prospectsByIds(ids);   // existing helper
    const { job_id } = await api.post('/v1/personalize/batch', {
      brand: 'lakeb2b',
      prospects: prospects.map(p => ({ name: p.name, title: p.title, domain: p.domain, linkedin: p.linkedin_url })),
      levels: [4, 5],   // ChampIQ's default — high-touch only
    });
    setBatchJobId(job_id);
  }}
>
  Personalize selected (5-level)
</button>
```

Render per-row 5-level chips from the polled job results. Pixie (ChampIQ's AI assistant) can summarise the brief in the row drawer.

## ChampMail · plain HTTP integration

If you'd rather not couple via a shared venv, use the HTTP client. Same shape:

```python
from champ_personalize import PersonalizerClient

client = PersonalizerClient(
    base_url=settings.personalizer_url,
    token=settings.personalizer_internal_jwt,
)
result = await client.personalize(brand="lakeb2b", prospect={...})
```

Trade-off: one extra hop per prospect, but the personalizer can scale independently.
