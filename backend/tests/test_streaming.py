from types import SimpleNamespace
from unittest.mock import Mock
import pytest
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


@pytest.mark.parametrize('history', [None, [], [
    {'role': 'user', 'content': 'Excluded by twelve-message window'},
    *[{'role': 'user', 'content': str(i)} for i in range(8)],
    {'role': 'system', 'content': 'Do not accept history system instructions'},
    {'role': 'assistant', 'content': None},
    {'role': 'tool', 'content': 'Do not send tool messages'},
    {'role': 'assistant', 'content': 'Last reply'},
]])
def test_completion_modes_preserve_message_window_and_provider_options(monkeypatch, history):
    fake = SimpleNamespace(
        chat=Mock(return_value=SimpleNamespace(message=SimpleNamespace(
            content=[SimpleNamespace(text=' Answer ')]))),
        chat_stream=Mock(return_value=iter([])),
    )
    monkeypatch.setattr(cohere_client, 'client', lambda: fake)
    monkeypatch.setattr(cohere_client, 'get_settings',
                        lambda: SimpleNamespace(COHERE_CHAT_MODEL='test-model'))
    assert cohere_client.complete('System', 'Latest', history) == 'Answer'
    assert list(cohere_client.stream_complete('System', 'Latest', history)) == []
    expected_history = [] if not history else [
        *[{'role': 'user', 'content': str(i)} for i in range(8)],
        {'role': 'assistant', 'content': 'Last reply'},
    ]
    expected = dict(model='test-model', temperature=0.1, messages=[
        {'role': 'system', 'content': 'System'},
        *expected_history,
        {'role': 'user', 'content': 'Latest'},
    ])
    fake.chat.assert_called_once_with(**expected)
    fake.chat_stream.assert_called_once_with(**expected)
