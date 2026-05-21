from __future__ import annotations

from typing import Any, Callable, Awaitable

from app.services.connectors import PushResult
from app.services.connectors import champiq, champmail, instantly


_CONNECTORS: dict[str, dict[str, Any]] = {
    instantly.PROVIDER: {
        "required": instantly.REQUIRED_FIELDS,
        "push": instantly.push,
        "healthcheck": instantly.healthcheck,
        "label": "Instantly",
    },
    champmail.PROVIDER: {
        "required": champmail.REQUIRED_FIELDS,
        "push": champmail.push,
        "healthcheck": champmail.healthcheck,
        "label": "ChampMail",
    },
    champiq.PROVIDER: {
        "required": champiq.REQUIRED_FIELDS,
        "push": champiq.push,
        "healthcheck": champiq.healthcheck,
        "label": "ChampIQ (webhook)",
    },
}


def list_providers() -> list[dict[str, Any]]:
    return [
        {"provider": p, "label": v["label"], "required": list(v["required"])}
        for p, v in _CONNECTORS.items()
    ]


def get_connector(provider: str) -> dict[str, Any]:
    if provider not in _CONNECTORS:
        raise LookupError(f"Unknown integration provider: {provider}")
    return _CONNECTORS[provider]


PushFn = Callable[[dict[str, Any], list[dict[str, Any]]], Awaitable[PushResult]]
