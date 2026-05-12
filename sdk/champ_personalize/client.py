from __future__ import annotations

from typing import Any, Iterable, Optional

import httpx

from champ_personalize.types import BatchResult, JobStatus, PersonalizeResult


class PersonalizerClient:
    """HTTP client for the Five-Level Email Personalizer service.

    Designed as a drop-in for ChampMail and ChampIQ integration:

        client = PersonalizerClient("https://personalize.lakeb2b.com", token="...")
        result = await client.personalize(
            brand="lakeb2b",
            prospect={"name": "Priya", "title": "VP Sales", "domain": "stripe.com"},
        )
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self, brand: Optional[str]) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if brand:
            h["X-Brand"] = brand
        return h

    async def _post(self, path: str, payload: dict[str, Any], brand: Optional[str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(f"{self._base}{path}", headers=self._headers(brand), json=payload)
        r.raise_for_status()
        return r.json()

    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self._base}{path}", headers=self._headers(None))
        r.raise_for_status()
        return r.json()

    async def personalize(
        self,
        *,
        brand: str,
        prospect: dict[str, Any],
        sender: Optional[dict[str, Any]] = None,
        levels: Iterable[int] = (1, 2, 3, 4, 5),
        model: Optional[str] = None,
    ) -> PersonalizeResult:
        payload = {
            "prospect": prospect,
            "sender": sender,
            "levels": list(levels),
            "provider": "openrouter",
            "model": model,
        }
        data = await self._post("/v1/personalize", payload, brand)
        return PersonalizeResult(**data)

    async def personalize_batch(
        self,
        *,
        brand: str,
        prospects: list[dict[str, Any]],
        sender: Optional[dict[str, Any]] = None,
        levels: Iterable[int] = (1, 2, 3, 4, 5),
        model: Optional[str] = None,
    ) -> BatchResult:
        payload = {
            "prospects": prospects,
            "sender": sender,
            "levels": list(levels),
            "provider": "openrouter",
            "model": model,
        }
        data = await self._post("/v1/personalize/batch", payload, brand)
        return BatchResult(**data)

    async def get_job(self, job_id: str) -> JobStatus:
        data = await self._get(f"/v1/jobs/{job_id}")
        return JobStatus(**data)
