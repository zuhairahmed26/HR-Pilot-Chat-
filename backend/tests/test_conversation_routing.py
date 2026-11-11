"""Routing regressions without network or database access."""
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
import pytest
from src.hr_management_agent.chat import api


def test_history_request_avoids_policy_search():
    history = [{'role':'user','content':'Earlier question'}]
    with patch.object(api, 'classify_intent', return_value='conversation_history'), \
         patch.object(api, 'search_policy') as search, \
         patch.object(api, 'complete', return_value='Earlier question'):
        answer, sources = api.response_for('What did I ask?', history, {})
        assert answer == 'Earlier question'
        assert sources == []
        search.assert_not_called()


def test_no_history_returns_honest_answer():
    with patch.object(api, 'classify_intent', return_value='conversation_history'):
        answer, sources = api.response_for('What was my first question?', [], {})
        assert 'no previous messages' in answer.lower()
        assert sources == []


@pytest.fixture
def routing(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = SimpleNamespace(chat_data=[])
    session = MagicMock()
    session.__enter__.return_value = db
    monkeypatch.setattr(api, 'SessionLocal', lambda: session)
    for name in ('has_active_opd_draft','has_active_draft','has_active_ticket_draft'):
        monkeypatch.setattr(api, name, lambda *args: True)
    handlers = {}
    for name in ('process_opd_message','process_leave_message','process_ticket_message'):
        handlers[name] = Mock(return_value='Workflow reply')
        monkeypatch.setattr(api, name, handlers[name])
    return handlers


def test_active_drafts_do_not_override_model(monkeypatch, routing):
    classifier = Mock(return_value='ticket_creation')
    monkeypatch.setattr(api, 'classify_intent', classifier)
    stream = api.stream_and_save('session', 'new ticket please', 1, {}, {}, provider='groq')
    assert next(stream) == 'Workflow reply'
    stream.close()
    routing['process_ticket_message'].assert_called_once()
    routing['process_opd_message'].assert_not_called()
    routing['process_leave_message'].assert_not_called()
    assert classifier.call_args.kwargs['active_workflows'] == ['opd_claim_request','leave_apply','ticket_creation']
    assert classifier.call_args.kwargs['provider'] == 'groq'


@pytest.mark.parametrize('result', ['opd_claim_request', 'hr_policy_qa', 'failure'])
def test_attachment_is_classified_and_unused_upload_cleaned(monkeypatch, routing, tmp_path, result):
    path = tmp_path / 'receipt.png'
    path.write_bytes(b'test')
    monkeypatch.setattr(api, 'STORAGE_DIR', tmp_path)
    classifier = Mock(return_value=result)
    if result == 'failure':
        classifier.side_effect = api.IntentClassificationError('Retry')
    monkeypatch.setattr(api, 'classify_intent', classifier)
    stream = api.stream_and_save('session', 'my receipt', 1, {}, {},
                                {'stored_filename':'receipt.png'}, provider='groq')
    if result == 'opd_claim_request':
        assert next(stream) == 'Workflow reply'
        assert path.exists()
        routing['process_opd_message'].assert_called_once()
    else:
        with pytest.raises(api.IntentClassificationError):
            next(stream)
        assert not path.exists()
        for handler in routing.values():
            handler.assert_not_called()
    stream.close()
    assert classifier.call_args.kwargs['has_attachment'] is True
