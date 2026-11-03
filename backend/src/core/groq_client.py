"""Groq text generation client for HR Pilot.

Standalone by design: existing Cohere, retrieval and HR workflow modules remain unchanged.
"""
from functools import lru_cache
import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from groq import Groq

# Explicit path also works when running snippets through PowerShell stdin.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / '.env')

DEFAULT_MODEL = 'qwen/qwen3.8-27b'


@lru_cache(maxsize=1)
def client() -> Groq:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise RuntimeError('GROQ_API_KEY is missing from backend/.env')
    return Groq(api_key=api_key, timeout=30.0, max_retries=0)


def model_name() -> str:
    return os.getenv('GROQ_MODEL', DEFAULT_MODEL)


def _messages(system: str, user: str, history: list[dict] | None) -> list[dict]:
    messages = [{'role': 'system', 'content': system}]
    for message in (history or [])[-12:]:
        if message.get('role') in ('user', 'assistant') and isinstance(message.get('content'), str):
            messages.append({'role': message['role'], 'content': message['content']})
    messages.append({'role': 'user', 'content': user})
    return messages


def complete(system: str, user: str, history: list[dict] | None = None,
             max_completion_tokens: int = 300) -> str:
    """Return the final text, excluding model reasoning or tool outputs."""
    response = client().chat.completions.create(
        model=model_name(),
        messages=_messages(system, user, history),
        temperature=0.1,
        reasoning_effort='none',
        max_completion_tokens=max_completion_tokens,
    )
    return (response.choices[0].message.content or '').strip()


def stream_complete(system: str, user: str, history: list[dict] | None = None,
                    max_completion_tokens: int = 400) -> Iterator[str]:
    """Yield only final-answer text fragments for existing SSE chat route."""
    stream = client().chat.completions.create(
        model=model_name(),
        messages=_messages(system, user, history),
        temperature=0.1,
        reasoning_effort='none',
        max_completion_tokens=max_completion_tokens,
        stream=True,
    )
    for event in stream:
        if not event.choices:
            continue
        content = event.choices[0].delta.content
        if content:
            yield content
