from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.database.database_connection import get_db
from src.database.models import Employee
from src.hr_management_agent.auth.authenticate import create_access_token, verify_password, get_current_employee

router = APIRouter(prefix='/api/hr/auth', tags=['Auth'])
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    first_login: bool
    last_login: datetime

@router.post('/login', response_model=TokenResponse)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.email == form_data.username.lower().strip(),
                                     Employee.is_deleted.is_(False), Employee.status == 'active').first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(401, 'Invalid credentials')
    first_login = user.last_login is None
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return dict(access_token=create_access_token(user),token_type='bearer',role=user.role,
                first_login=first_login,last_login=user.last_login)

@router.get('/employees/current_employee')
def current_employee(user: dict = Depends(get_current_employee)):
    return user
