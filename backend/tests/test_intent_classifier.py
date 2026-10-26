import json
from types import SimpleNamespace
from unittest.mock import patch
from src.hr_management_agent.chat.intent_classifier import classify_intent, fallback_classify


def mock_response(label):
    return SimpleNamespace(message=SimpleNamespace(content=[SimpleNamespace(text=json.dumps({'intent': label}))]))


def test_history_bypasses_model():
    with patch('src.hr_management_agent.chat.intent_classifier.client') as provider:
        assert classify_intent('What was my very first question in this conversation?') == 'conversation_history'
        provider.assert_not_called()


def test_structured_classification():
    fake = SimpleNamespace(chat=lambda **kwargs: mock_response('leave_balance_inquiry'))
    with patch('src.hr_management_agent.chat.intent_classifier.client', return_value=fake):
        assert classify_intent('How many vacation days do I personally have left?') == 'leave_balance_inquiry'


def test_invalid_label_falls_back():
    fake = SimpleNamespace(chat=lambda **kwargs: mock_response('send_money'))
    with patch('src.hr_management_agent.chat.intent_classifier.client', return_value=fake):
        assert classify_intent('What is the annual leave policy?') == 'hr_policy_qa'


def test_provider_error_falls_back():
    fake = SimpleNamespace(chat=lambda **kwargs: (_ for _ in ()).throw(RuntimeError('offline')))
    with patch('src.hr_management_agent.chat.intent_classifier.client', return_value=fake):
        assert classify_intent('Please create ticket for my laptop') == 'ticket_creation'


def test_policy_vs_balance_fallback():
    assert fallback_classify('What is the annual leave entitlement policy?') == 'hr_policy_qa'
    assert fallback_classify('What is my remaining leave balance?') == 'leave_balance_inquiry'
