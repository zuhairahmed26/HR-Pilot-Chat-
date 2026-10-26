from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.database_connection import Base

def utcnow(): return datetime.now(timezone.utc)

class Employee(Base):
    __tablename__ = 'employees'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(50), default='user')
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leave_balances: Mapped[dict | None] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default='active')
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat_histories: Mapped[list['HRChatHistory']] = relationship(back_populates='employee', cascade='all, delete-orphan')

class HRChatHistory(Base):
    __tablename__ = 'hr_chathistory'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    chat_title: Mapped[str] = mapped_column(Text, default='New Chat')
    chat_data: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    employee: Mapped['Employee'] = relationship(back_populates='chat_histories')

class PolicyDocument(Base):
    __tablename__ = 'policy_documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('employees.id'))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
