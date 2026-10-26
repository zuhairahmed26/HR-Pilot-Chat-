"""Focused regression tests for conversation-history routing."""
from unittest.mock import patch
from src.hr_management_agent.chat import api


def test_history_request_avoids_policy_search():
    history = [
        {'role': 'user', 'content': 'Explain the annual leave entitlement and carry-forward rules in detail.'},
        {'role': 'assistant', 'content': 'The handbook allows 18 days.'},
    ]
    with patch.object(api, 'search_policy', side_effect=AssertionError('Should not query Qdrant')):
        with patch.object(api, 'complete', return_value='Your first question was ...') as complete:
            answer, sources = api.response_for(
                'What was my very first question in this conversation? Repeat it exactly.',
                history, {},
            )
            assert 'first question' in answer
            assert sources == []
            complete.assert_called_once()


def test_no_history_returns_honest_answer():
    with patch.object(api, 'search_policy', side_effect=AssertionError('Should not query Qdrant')):
        answer, sources = api.response_for('What was my first question in this chat?', [], {})
        assert 'no previous messages' in answer.lower()
        assert sources == []


def test_normal_policy_question_still_uses_rag():
    assert api.asks_about_conversation('What was my first question in this conversation?')
    assert not api.asks_about_conversation('How many annual leave days can I carry forward?')
