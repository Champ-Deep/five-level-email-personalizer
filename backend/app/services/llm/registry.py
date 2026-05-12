from app.services.llm.base import LLMError, LLMProvider
from app.services.llm.openrouter import OpenRouterProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openrouter": OpenRouterProvider,
}


def get_provider(name: str = "openrouter") -> LLMProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise LLMError(f"Unknown LLM provider: {name}. Available: {list(_PROVIDERS)}")
    return cls()
