from datetime import timedelta, date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from src.hr_management_agent.opd.service import validate_claim


def test_valid_claim():
    amount, treatment, description = validate_claim('1250.50', '2026-10-01', 'Doctor consultation')
    assert amount == Decimal('1250.50')
    assert treatment == date(2026, 10, 1)
    assert description == 'Doctor consultation'


@pytest.mark.parametrize('amount', ['-1', '0', 'NaN', 'Infinity', '12.345', 'abc'])
def test_invalid_amount(amount):
    with pytest.raises(HTTPException):
        validate_claim(amount, '2026-10-01', 'Doctor consultation')


def test_future_date_rejected():
    with pytest.raises(HTTPException):
        validate_claim('100', (date.today() + timedelta(days=1)).isoformat(), 'Doctor consultation')


def test_short_description_rejected():
    with pytest.raises(HTTPException):
        validate_claim('100', '2026-10-01', 'abc')
