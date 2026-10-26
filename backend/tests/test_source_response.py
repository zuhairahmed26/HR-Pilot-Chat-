"""Run after installing requirements: python -m pytest tests/test_source_response.py -q"""
from src.hr_management_agent.chat.api import public_policy_sources


def test_sources_hide_full_text_and_deduplicate_pages():
    refs = [
        {"filename": "handbook.pdf", "page": 1, "score": 0.63981855, "text": "Confidential full page text"},
        {"filename": "handbook.pdf", "page": 1, "score": 0.52, "text": "Different chunk on same page"},
        {"filename": "handbook.pdf", "page": 2, "score": 0.44856, "text": "More confidential content"},
    ]
    result = public_policy_sources(refs)
    assert result == [
        {"filename": "handbook.pdf", "page": 1, "score": 0.6398},
        {"filename": "handbook.pdf", "page": 2, "score": 0.4486},
    ]
    assert "Confidential" not in str(result)


def test_sources_handles_empty():
    assert public_policy_sources([]) == []
