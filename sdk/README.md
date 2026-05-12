# champ-personalize

Python SDK for the Champions Group **Five-Level Email Personalizer** service.

Two clients, one package:

- `PersonalizerClient` — HTTP client. Use for cross-service calls (ChampIQ → personalizer service, third parties).
- `LocalPersonalizer` — in-process adapter. Use when you can install the backend package alongside (e.g. inside ChampMail's worker).

## Install

```bash
pip install champ-personalize             # HTTP client only
pip install champ-personalize[local]      # + in-process adapter (requires backend on PYTHONPATH)
```

## HTTP usage

```python
from champ_personalize import PersonalizerClient

client = PersonalizerClient("https://personalize.lakeb2b.com", token="<jwt>")

result = await client.personalize(
    brand="lakeb2b",
    prospect={"name": "Priya Sharma", "title": "VP Sales", "domain": "stripe.com"},
)
for level, draft in result.emails.items():
    print(level, draft.subject)
```

## In-process usage (ChampMail integration target)

```python
from champ_personalize.local import LocalPersonalizer

personalizer = LocalPersonalizer(brand="lakeb2b")
result = await personalizer.run(
    {"name": "Priya", "title": "VP Sales", "domain": "stripe.com"},
    levels=[4],
)
```

## Batch

```python
batch = await client.personalize_batch(
    brand="lakeb2b",
    prospects=[{...}, {...}, ...],
)
# Poll for completion:
job = await client.get_job(batch.job_id)
while job.status not in ("completed", "completed_with_failures"):
    await asyncio.sleep(2.5)
    job = await client.get_job(batch.job_id)
```
