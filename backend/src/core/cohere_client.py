from functools import lru_cache
import cohere
from src.core.config import get_settings

@lru_cache
def client():
    return cohere.ClientV2(api_key=get_settings().COHERE_API_KEY)

def extract_text(response) -> str:
    items = response.message.content or []
    return ''.join(getattr(item, 'text', '') or '' for item in items).strip()

def _messages(system: str, user: str, history: list[dict] | None) -> list[dict]:
    """Build the same bounded conversation for both completion modes."""
    messages = [{'role':'system','content':system}]
    for msg in (history or [])[-12:]:
        if msg.get('role') in ('user','assistant') and isinstance(msg.get('content'), str):
            messages.append({'role':msg['role'],'content':msg['content']})
    messages.append({'role':'user','content':user})
    return messages


def complete(system: str, user: str, history: list[dict] | None = None) -> str:
    messages = _messages(system, user, history)
    result = client().chat(model=get_settings().COHERE_CHAT_MODEL,messages=messages,temperature=0.1)
    return extract_text(result)


def stream_complete(system: str, user: str, history: list[dict] | None = None):
    """Yield Cohere v2 content-delta fragments as they arrive."""
    messages = _messages(system, user, history)
    events = client().chat_stream(
        model=get_settings().COHERE_CHAT_MODEL,
        messages=messages,
        temperature=0.1,
    )
    for event in events:
        if event.type == 'content-delta':
            delta = event.delta.message.content.text
            if delta:
                yield delta
