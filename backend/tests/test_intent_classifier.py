import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src.hr_management_agent.chat import intent_classifier as classifier


@pytest.mark.parametrize('provider', ['cohere', 'groq'])
@pytest.mark.parametrize('query', [
    'I want annual leave', 'Create a ticket for my laptop',
    'What was my first question in this chat?', 'What is the OPD policy?', 'yes',
])
def test_every_message_uses_selected_model(monkeypatch, provider, query):
    raw = '{"intent":"hr_policy_qa"}'
    chat = Mock(return_value=SimpleNamespace(message=SimpleNamespace(content=[SimpleNamespace(text=raw)])))
    complete = Mock(return_value=raw)
    monkeypatch.setattr(classifier, 'cohere_client', lambda: SimpleNamespace(chat=chat))
    monkeypatch.setattr(classifier, 'complete', complete)
    monkeypatch.setattr(classifier, 'get_settings', lambda: SimpleNamespace(COHERE_CHAT_MODEL='test'))
    # Deliberately return a label different from former shortcuts: model output wins.
    assert classifier.classify_intent(query, provider=provider) == 'hr_policy_qa'
    (chat if provider == 'cohere' else complete).assert_called_once()
    (complete if provider == 'cohere' else chat).assert_not_called()


def test_context_reaches_model(monkeypatch):
    complete = Mock(return_value='```json\n{"intent":"leave_apply"}\n```')
    monkeypatch.setattr(classifier, 'complete', complete)
    history = [{'role':'assistant', 'content':'Confirm annual leave?'}]
    assert classifier.classify_intent('yes', history, 'groq',
        active_workflows=['leave_apply'], has_attachment=True) == 'leave_apply'
    prompt = complete.call_args.args[1].split('Output a JSON object: ', 1)[1]
    data = json.loads(prompt)
    assert data == {'history':history, 'latest_user_message':'yes',
                    'active_workflows':['leave_apply'], 'has_attachment':True}


@pytest.mark.parametrize('raw', ['not json', '{"intent":"send_money"}', '{}',
    '{"intent":"leave_apply","approved":true}', '[]'])
def test_bad_model_output_never_falls_back(monkeypatch, raw):
    monkeypatch.setattr(classifier, 'complete', Mock(return_value=raw))
    with pytest.raises(classifier.IntentClassificationError):
        classifier.classify_intent('Create a ticket for my laptop', provider='groq')


@pytest.mark.parametrize('provider', ['cohere', 'groq'])
def test_outage_never_falls_back(monkeypatch, provider):
    failed = Mock(side_effect=RuntimeError('offline'))
    monkeypatch.setattr(classifier, 'complete', failed)
    monkeypatch.setattr(classifier, 'cohere_client', failed)
    with pytest.raises(classifier.IntentClassificationError):
        classifier.classify_intent('Apply for leave', provider=provider)
