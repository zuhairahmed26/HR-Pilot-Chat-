"""Isolated, confirmation-gated leave workflow (NO Odoo/approval/balance mutation).

Drafts are not submitted applications. Only an explicit affirmative confirmation
turns a valid draft into a locally stored pending application.
"""
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Date, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.core.cohere_client import client, extract_text
from src.core.config import get_settings
from src.database.database_connection import Base, SessionLocal

log = logging.getLogger(__name__)
DRAFT_LIFETIME = timedelta(minutes=30)


class LeaveDraft(Base):
    __tablename__ = 'cohere_leave_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    state: Mapped[str] = mapped_column(String(40), default='collecting', nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeaveRequest(Base):
    __tablename__ = 'cohere_leave_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(Integer, ForeignKey('cohere_leave_drafts.id'), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeaveFields(BaseModel):
    leave_type: Literal['annual', 'casual', 'medical'] | None = None
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def active_draft(db: Session, session_id: str, employee_id: int) -> LeaveDraft | None:
    draft = db.scalar(select(LeaveDraft).where(LeaveDraft.session_id == session_id,
                                                 LeaveDraft.employee_id == employee_id))
    if draft and draft.state in ('collecting', 'confirming'):
        if _aware(draft.expires_at) > now_utc():
            return draft
        draft.state = 'expired'
        db.commit()
    return None


def has_active_draft(session_id: str, employee_id: int) -> bool:
    with SessionLocal() as db:
        return active_draft(db, session_id, employee_id) is not None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _validate(details: dict) -> list[str]:
    issues: list[str] = []
    if details.get('leave_type') not in ('annual', 'casual', 'medical'):
        issues.append('leave type (annual, casual, or medical)')
    start = _parse_date(details.get('start_date'))
    end = _parse_date(details.get('end_date'))
    if not start:
        issues.append('start date in YYYY-MM-DD format')
    if not end:
        issues.append('end date in YYYY-MM-DD format')
    if start and end:
        if start < now_utc().date():
            issues.append('a start date that is today or later')
        if end < start:
            issues.append('an end date on or after the start date')
        if (end - start).days > 365:
            issues.append('a date range of at most one year')
    if not isinstance(details.get('reason'), str) or not details['reason'].strip():
        issues.append('reason for leave')
    return issues


def _explicit_leave_fields(message: str) -> dict:
    """Extract only unambiguous, explicitly written details without an LLM.

    Supports e.g. 'annual leave from 2026-11-02 to 2026-11-04 for a family visit'.
    Never guesses dates or a reason. Other wordings fall through to Cohere.
    """
    lowered = message.casefold()
    types = [t for t in ('annual', 'casual', 'medical')
             if re.search(r'\b' + t + r'\s+leave\b', lowered)]
    if len(types) != 1:
        return {}
    match = re.search(
        r'\bfrom\s+(\d{4}-\d{2}-\d{2})\s+to\s+'
        r'(\d{4}-\d{2}-\d{2})\s+for\s+(.+?)\s*[.!?]?\s*$',
        message, re.IGNORECASE | re.DOTALL
    )
    if not match:
        return {}
    start, end, reason = match.groups()
    reason = reason.strip().rstrip('.!?').strip()
    if not (_parse_date(start) and _parse_date(end) and reason):
        return {}
    return dict(leave_type=types[0], start_date=start, end_date=end,
                reason=reason[:500])


def _extract(message: str, history: list[dict], existing: dict) -> dict:
    """Use deterministic extraction for clear dates, otherwise Cohere."""
    explicit = _explicit_leave_fields(message)
    if explicit:
        return explicit
    prior = [m for m in history[-8:] if m.get('role') in ('user', 'assistant')]
    prompt = json.dumps({
        'today_utc': now_utc().date().isoformat(),
        'previous_details': existing,
        'recent_messages': prior,
        'new_message': message,
    }, ensure_ascii=False)
    response = client().chat(
        model=get_settings().COHERE_CHAT_MODEL,
        messages=[
            {'role': 'system', 'content': (
                'Extract leave request fields. Return JSON only, keys: leave_type, start_date, '
                'end_date, reason. leave_type must be annual, casual, medical or null. Dates '
                'must be explicit, unambiguous ISO YYYY-MM-DD or null. Do not invent or '
                'assume dates from vague references such as next week or Monday. '
                'Only include new values actually supplied by the user; use null for all others. '
                'Never infer a leave reason. Do not assume submission or approval.'
            )},
            {'role': 'user', 'content': prompt},
        ],
        response_format={'type': 'json_object'},
        temperature=0,
    )
    fields = LeaveFields.model_validate(json.loads(extract_text(response)))
    updates = fields.model_dump(exclude_none=True)
    if 'reason' in updates:
        updates['reason'] = updates['reason'].strip()[:500]
    return updates


def _summary(details: dict) -> str:
    return (f"Please confirm your LOCAL leave request:\n"
            f"- Type: {details['leave_type']}\n"
            f"- Start: {details['start_date']}\n"
            f"- End: {details['end_date']}\n"
            f"- Reason: {details['reason']}\n\n"
            'Reply **yes** to submit this as a *pending* request in the prototype, '
            'or **no** to cancel. This will not contact Odoo, deduct leave balance, '
            'or approve leave.')


def process_leave_message(session_id: str, employee_id: int, message: str,
                          history: list[dict]) -> str:
    """Called only for an active draft or the leave_apply intent.

    A confirmed request is committed once, keyed by draft_id. Approval is external.
    """
    message = message.strip()
    lowered = message.casefold().strip(' .!')
    yes = lowered in ('yes', 'yes confirm', 'confirm', 'submit', 'submit request')
    no = lowered in ('no', 'cancel', 'cancel request', 'never mind', 'nevermind')
    with SessionLocal.begin() as db:
        draft = db.scalar(select(LeaveDraft).where(LeaveDraft.session_id == session_id,
                                                  LeaveDraft.employee_id == employee_id).with_for_update())
        if draft and _aware(draft.expires_at) <= now_utc() and draft.state in ('collecting', 'confirming'):
            draft.state = 'expired'
        if draft and draft.state not in ('collecting', 'confirming'):
            draft = None
        if no:
            if draft:
                draft.state = 'cancelled'
                return 'Your unsubmitted leave draft has been cancelled. No leave request was created.'
            return 'There is no active leave draft to cancel.'
        if yes:
            if not draft or draft.state != 'confirming':
                return 'There is no completed leave draft awaiting confirmation. Please provide your leave details first.'
            issues = _validate(draft.details)
            if issues:
                draft.state = 'collecting'
                return 'Before submitting, please provide: ' + '; '.join(issues) + '.'
            existing = db.scalar(select(LeaveRequest).where(LeaveRequest.draft_id == draft.id))
            if existing:
                draft.state = 'submitted'
                return f'Leave request #{existing.id} was already submitted; status: {existing.status}.'
            record = LeaveRequest(
                draft_id=draft.id, session_id=session_id, employee_id=employee_id,
                leave_type=draft.details['leave_type'],
                start_date=_parse_date(draft.details['start_date']),
                end_date=_parse_date(draft.details['end_date']),
                reason=draft.details['reason'], status='pending', created_at=now_utc(),
            )
            db.add(record)
            db.flush()
            draft.state = 'submitted'
            return (f'Leave request #{record.id} has been saved locally with status **pending**. '
                    'It has not been approved, and no leave balance was deducted or Odoo action performed.')
        previous = dict(draft.details) if draft else {}
    # Network call outside DB transaction/row lock.
    try:
        updates = _extract(message, history, previous)
    except Exception:
        log.exception('Leave detail extraction failed')
        return ('I could not interpret the leave details right now. Please retry with '
                'type, exact dates (YYYY-MM-DD), and reason. No request was submitted.')
    merged = {**previous, **updates}
    issues = _validate(merged)
    with SessionLocal.begin() as db:
        draft = db.scalar(select(LeaveDraft).where(LeaveDraft.session_id == session_id,
                                                  LeaveDraft.employee_id == employee_id).with_for_update())
        # Do not reopen a submitted draft when the client retries the same session.
        if draft and draft.state == 'submitted':
            return 'The previous leave draft has already been submitted. Start a new chat for another application.'
        if draft and draft.state in ('cancelled', 'expired'):
            draft.details = merged
            draft.state = 'collecting'
        if not draft:
            draft = LeaveDraft(session_id=session_id, employee_id=employee_id,
                               details=merged, state='collecting', updated_at=now_utc(),
                               expires_at=now_utc() + DRAFT_LIFETIME)
            db.add(draft)
        else:
            draft.details = merged
            draft.updated_at = now_utc()
            draft.expires_at = now_utc() + DRAFT_LIFETIME
        draft.state = 'collecting' if issues else 'confirming'
    if issues:
        return ('To prepare your leave request, please provide: ' + '; '.join(issues) + '. '
                'No request has been submitted.')
    return _summary(merged)


def list_leave_requests(employee_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(select(LeaveRequest).where(LeaveRequest.employee_id == employee_id)
                          .order_by(LeaveRequest.id.desc())).all()
        return [dict(id=r.id, leave_type=r.leave_type,
                     start_date=r.start_date.isoformat(), end_date=r.end_date.isoformat(),
                     reason=r.reason, status=r.status,
                     created_at=r.created_at.isoformat()) for r in rows]
