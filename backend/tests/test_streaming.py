from types import SimpleNamespace
from src.core import cohere_client


def test_stream_complete_emits_only_text_deltas(monkeypatch):
    seen = {}
    def fake_stream(**kwargs):
        seen.update(kwargs)
        for part in ['Hello', ' world']:
            yield SimpleNamespace(type='content-delta', delta=SimpleNamespace(message=SimpleNamespace(content=SimpleNamespace(text=part))))
        yield SimpleNamespace(type='message-end')
    monkeypatch.setattr(cohere_client, 'client', lambda: SimpleNamespace(chat_stream=fake_stream))
    monkeypatch.setattr(cohere_client, 'get_settings', lambda: SimpleNamespace(COHERE_CHAT_MODEL='test-model'))
    chunks = list(cohere_client.stream_complete('System', 'Question', [{'role':'user','content':'Earlier'}]))
    assert chunks == ['Hello', ' world']
    assert seen['messages'][-1] == {'role': 'user', 'content': 'Question'}


def test_compact_citations_unchanged():
    from src.hr_management_agent.chat.api import public_policy_sources
    sources = public_policy_sources([
        {'filename': 'test.pdf', 'page': 1, 'score': 0.67, 'text': 'private'},
        {'filename': 'test.pdf', 'page': 1, 'score': 0.52, 'text': 'private2'},
    ])
    assert sources == [{'filename': 'test.pdf', 'page': 1, 'score': 0.67}]
