from datetime import timedelta, datetime, timezone
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
