"""Select Cohere or Groq for HR Pilot text generation.

Does not change retrieval, embedding, transaction, or OPD workflows.
"""
from typing import Iterator

from src.core import cohere_client, groq_client

SUPPORTED_PROVIDERS = frozenset({'cohere', 'groq'})


def normalize_provider(provider: str = 'cohere') -> str:
    if not isinstance(provider, str):
        raise ValueError('Provider must be cohere or groq')
    selected = provider.strip().lower()
    if selected not in SUPPORTED_PROVIDERS:
        raise ValueError('Provider must be cohere or groq')
    return selected


def complete(system: str, user: str, history: list[dict] | None = None,
             provider: str = 'cohere', max_completion_tokens: int = 300) -> str:
    selected = normalize_provider(provider)
    if selected == 'groq':
        return groq_client.complete(system, user, history, max_completion_tokens=max_completion_tokens)
    return cohere_client.complete(system, user, history)


def stream_complete(system: str, user: str, history: list[dict] | None = None,
                    provider: str = 'cohere', max_completion_tokens: int = 400) -> Iterator[str]:
    selected = normalize_provider(provider)
    if selected == 'groq':
        yield from groq_client.stream_complete(system, user, history, max_completion_tokens=max_completion_tokens)
    else:
        yield from cohere_client.stream_complete(system, user, history)
