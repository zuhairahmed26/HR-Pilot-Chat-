"""Local prototype support tickets; no external delivery or staff assignment."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from src.database.database_connection import Base, SessionLocal

TTL = timedelta(minutes=30)

class TicketDraft(Base):
    __tablename__ = 'cohere_ticket_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default='confirming')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SupportTicket(Base):
    __tablename__ = 'cohere_support_tickets'
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(Integer, ForeignKey('cohere_ticket_drafts.id'), unique=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='open')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

def now():
    return datetime.now(timezone.utc)

def aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def has_active_ticket_draft(session_id: str, employee_id: int) -> bool:
    with SessionLocal() as db:
        draft = db.scalar(select(TicketDraft).where(TicketDraft.session_id == session_id, TicketDraft.employee_id == employee_id))
        return bool(draft and draft.state == 'confirming' and aware(draft.expires_at) > now())

def process_ticket_message(session_id: str, employee_id: int, message: str) -> str:
    answer = message.strip().lower().strip(' .!')
    confirm = answer in ('yes', 'yes confirm', 'confirm', 'submit', 'submit ticket')
    cancel = answer in ('no', 'cancel', 'cancel ticket', 'never mind', 'nevermind')
    with SessionLocal.begin() as db:
        draft = db.scalar(select(TicketDraft).where(TicketDraft.session_id == session_id,
                      TicketDraft.employee_id == employee_id).with_for_update())
        if draft and draft.state == 'confirming' and aware(draft.expires_at) <= now():
            draft.state = 'expired'
        if confirm:
            if not draft or draft.state != 'confirming':
                if draft and draft.state == 'submitted':
                    ticket = db.scalar(select(SupportTicket).where(SupportTicket.draft_id == draft.id))
                    if ticket:
                        return f'Ticket #{ticket.id} was already submitted; status: {ticket.status}.'
                return 'No active support-ticket draft is awaiting confirmation.'
            ticket = db.scalar(select(SupportTicket).where(SupportTicket.draft_id == draft.id))
            if ticket:
                draft.state = 'submitted'
                return f'Ticket #{ticket.id} was already submitted; status: {ticket.status}.'
            ticket = SupportTicket(draft_id=draft.id, employee_id=employee_id,
                                   description=draft.description, status='open', created_at=now())
            db.add(ticket)
            db.flush()
            draft.state = 'submitted'
            return f'Support ticket #{ticket.id} has been created locally with status **open**. No external helpdesk was contacted.'
        if cancel:
            if draft and draft.state == 'confirming':
                draft.state = 'cancelled'
                return 'Ticket draft cancelled. No ticket was created.'
            return 'No active support-ticket draft to cancel.'
        if draft and draft.state == 'confirming':
            # Avoid replacing the description with an unrelated follow-up.
            return (f'Confirm ticket description: {draft.description}\n\n'
                    'Reply **yes** to create an open local support ticket or **no** to cancel.')
        if draft and draft.state == 'submitted':
            return 'This session already submitted a ticket. Start a new chat to create another.'
        description = message.strip()[:2000]
        if len(description) < 12:
            return 'Please describe the issue in more detail before creating a support ticket.'
        if draft:
            draft.description = description
            draft.state = 'confirming'
            draft.expires_at = now() + TTL
        else:
            db.add(TicketDraft(session_id=session_id, employee_id=employee_id,
                               description=description, state='confirming', expires_at=now()+TTL))
        return (f'Confirm ticket description: {description}\n\n'
                'Reply **yes** to create an open local support ticket or **no** to cancel.')

def list_tickets(employee_id: int) -> list[dict]:
    with SessionLocal() as db:
        records = db.scalars(select(SupportTicket).where(SupportTicket.employee_id == employee_id)
                             .order_by(SupportTicket.id.desc())).all()
        return [{'id': t.id, 'description': t.description, 'status': t.status,
                 'created_at': t.created_at.isoformat()} for t in records]
