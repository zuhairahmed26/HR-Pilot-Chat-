from datetime import timedelta, datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src.hr_management_agent.leave import service
from src.hr_management_agent.leave.service import _validate, _summary


def test_missing_details_require_collection():
    assert _validate({})


def test_complete_future_request_needs_confirmation():
    start = datetime.now(timezone.utc).date() + timedelta(days=8)
    details = dict(leave_type='annual', start_date=start.isoformat(),
                   end_date=(start + timedelta(days=2)).isoformat(), reason='Family visit')
    assert _validate(details) == []
    assert 'Reply **yes**' in _summary(details)


def test_invalid_range_rejected():
    start = datetime.now(timezone.utc).date() + timedelta(days=8)
    details = dict(leave_type='annual', start_date=start.isoformat(),
                   end_date=(start - timedelta(days=2)).isoformat(), reason='Family visit')
    assert any('end date' in issue for issue in _validate(details))


@pytest.mark.parametrize('message', [
    'I want annual leave from 2026-12-01 to 2026-12-03 for a family visit',
    'from 10TH nov to 12 th nov, need annual leave',
    'I need leave',
])
def test_leave_details_always_use_model(monkeypatch, message):
    # Returning no fields proves even the former exact pattern cannot bypass AI.
    response = SimpleNamespace(message=SimpleNamespace(content=[
        SimpleNamespace(text=json.dumps({'leave_type': None, 'start_date': None,
                                        'end_date': None, 'reason': None}))]))
    chat = Mock(return_value=response)
    monkeypatch.setattr(service, 'client', lambda: SimpleNamespace(chat=chat))
    monkeypatch.setattr(service, 'get_settings',
                        lambda: SimpleNamespace(COHERE_CHAT_MODEL='test-model'))
    history = [{'role':'assistant', 'content':'Which dates?'}]
    existing = {'leave_type':'annual'}
    assert service._extract(message, history, existing) == {}
    chat.assert_called_once()
    payload = json.loads(chat.call_args.kwargs['messages'][1]['content'])
    assert payload['new_message'] == message
    assert payload['previous_details'] == existing
    assert payload['recent_messages'] == history


def test_exact_wording_does_not_fall_back_when_model_fails(monkeypatch):
    chat = Mock(side_effect=RuntimeError('Provider unavailable'))
    monkeypatch.setattr(service, 'client', lambda: SimpleNamespace(chat=chat))
    monkeypatch.setattr(service, 'get_settings',
                        lambda: SimpleNamespace(COHERE_CHAT_MODEL='test-model'))
    with pytest.raises(RuntimeError, match='Provider unavailable'):
        service._extract('annual leave from 2026-12-01 to 2026-12-03 for family', [], {})
    chat.assert_called_once()
