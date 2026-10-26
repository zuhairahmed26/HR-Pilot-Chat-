"""Local OPD reimbursements. Files remain private; claims are never auto-approved."""
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from src.database.database_connection import Base, SessionLocal

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED = {
    'application/pdf': ('.pdf', b'%PDF-'),
    'image/png': ('.png', b'\x89PNG\r\n\x1a\n'),
    'image/jpeg': ('.jpg', b'\xff\xd8\xff'),
}
# Private, local directory outside any frontend static root. Override with an absolute path.
STORAGE_DIR = Path(os.getenv('OPD_UPLOAD_DIR', str(Path.cwd() / 'private_uploads' / 'opd'))).resolve()


class OPDClaim(Base):
    __tablename__ = 'cohere_opd_claims'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    treatment_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def validate_claim(amount: str, treatment_date: str, description: str) -> tuple[Decimal, date, str]:
    try:
        parsed = Decimal(amount)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(422, 'Claim amount must be a valid number')
    if not parsed.is_finite() or parsed <= 0 or parsed > Decimal('9999999999.99') or parsed.as_tuple().exponent < -2:
        raise HTTPException(422, 'Amount must be positive, at most 2 decimal places, and within range')
    try:
        parsed_date = date.fromisoformat(treatment_date)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Treatment date must be YYYY-MM-DD')
    if parsed_date > datetime.now().date():
        raise HTTPException(422, 'Treatment date cannot be in the future')
    description = description.strip()
    if not 5 <= len(description) <= 1000:
        raise HTTPException(422, 'Description must be 5 to 1000 characters')
    return parsed, parsed_date, description


def public_claim(claim: OPDClaim) -> dict:
    return {
        'id': claim.id, 'amount': str(claim.amount),
        'treatment_date': claim.treatment_date.isoformat(), 'description': claim.description,
        'filename': claim.original_filename, 'file_size': claim.file_size,
        'content_type': claim.content_type, 'status': claim.status,
        'created_at': claim.created_at.isoformat(),
        'attachment_url': f'/api/hr/chat/opd_claims/{claim.id}/attachment',
    }


def list_claims(employee_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(select(OPDClaim).where(OPDClaim.employee_id == employee_id).order_by(OPDClaim.id.desc())).all()
        return [public_claim(row) for row in rows]


def get_claim(employee_id: int, claim_id: int) -> OPDClaim:
    with SessionLocal() as db:
        claim = db.scalar(select(OPDClaim).where(OPDClaim.id == claim_id, OPDClaim.employee_id == employee_id))
        if not claim:
            raise HTTPException(404, 'OPD claim not found')
        db.expunge(claim)
        return claim


async def create_claim(employee_id: int, amount: str, treatment_date: str,
                       description: str, attachment: UploadFile) -> dict:
    parsed_amount, parsed_date, parsed_description = validate_claim(amount, treatment_date, description)
    mime = attachment.content_type
    if mime not in ALLOWED:
        raise HTTPException(415, 'Upload a PDF, JPEG, or PNG file')
    extension, magic = ALLOWED[mime]
    original = Path((attachment.filename or '').replace('\\', '/')).name
    if not original or len(original) > 255:
        raise HTTPException(422, 'Invalid attachment filename')
    valid_extensions = {'.jpg', '.jpeg'} if mime == 'image/jpeg' else {extension}
    if Path(original).suffix.lower() not in valid_extensions:
        raise HTTPException(415, 'File extension and declared content type do not match')

    STORAGE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored_name = uuid.uuid4().hex + extension
    target = STORAGE_DIR / stored_name
    size = 0
    try:
        first = await attachment.read(16)
        if not first.startswith(magic):
            raise HTTPException(415, 'File contents do not match the selected file type')
        with target.open('xb') as dest:
            chunk = first
            while chunk:
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Attachment cannot exceed 10 MB')
                dest.write(chunk)
                chunk = await attachment.read(1024 * 1024)
        if size == 0:
            raise HTTPException(422, 'Attachment cannot be empty')
        with SessionLocal.begin() as db:
            claim = OPDClaim(employee_id=employee_id, amount=parsed_amount, treatment_date=parsed_date,
                             description=parsed_description, original_filename=original,
                             stored_filename=stored_name, content_type=mime, file_size=size,
                             status='pending', created_at=datetime.now(timezone.utc))
            db.add(claim)
            db.flush()
            payload = public_claim(claim)
        return payload
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await attachment.close()
