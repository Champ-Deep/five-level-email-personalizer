"""In-process adapter — for ChampMail and ChampIQ to use the personalizer as a library.

Requires the `champ-personalize-backend` package to be importable, i.e. install with:

    pip install champ-personalize[local]

This is the zero-HTTP-overhead path. Use `PersonalizerClient` from `champ_personalize.client`
if you'd rather call the running service over HTTP.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from champ_personalize.types import PersonalizeResult


class LocalPersonalizer:
    """Imports the backend personalizer module directly. No HTTP."""

    def __init__(self, brand: str, *, provider: str = "openrouter") -> None:
        from app.services.brand_service import load_brand
        from app.services.llm.registry import get_provider

        self.brand = load_brand(brand)
        self._provider = get_provider(provider)

    async def run(
        self,
        prospect: dict[str, Any],
        *,
        sender: Optional[dict[str, Any]] = None,
        levels: Iterable[int] = (1, 2, 3, 4, 5),
        model: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> PersonalizeResult:
        from app.levels.schemas import ProspectInput, SenderInput
        from app.services.personalizer import personalize_one

        sender_in = SenderInput(**sender) if sender else None
        result = await personalize_one(
            ProspectInput(**prospect),
            self.brand,
            self._provider,
            sender=sender_in,
            levels=list(levels),
            model=model,
            system_prompt_override=system_prompt_override,
        )
        return PersonalizeResult(**result.model_dump(mode="json"))
