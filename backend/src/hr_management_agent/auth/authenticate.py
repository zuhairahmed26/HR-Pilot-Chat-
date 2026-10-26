from datetime import datetime, timezone, timedelta
from typing import Annotated
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from src.core.config import get_settings
from src.database.database_connection import get_db
from src.database.models import Employee

bearer = OAuth2PasswordBearer(tokenUrl='/api/hr/auth/login')

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError): return False

def create_access_token(user: Employee) -> str:
    s = get_settings()
    payload = {'sub': user.email, 'id': user.id, 'role': user.role, 'name': user.name,
               'leave_balances': user.leave_balances or {}, 'exp': datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, s.SECRET_KEY, algorithm=s.ALGORITHM)

def get_current_employee(token: Annotated[str, Depends(bearer)], db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    try:
        claims = jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITHM])
        employee_id = int(claims['id'])
        email = claims['sub']
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(401, 'Invalid or expired token', headers={'WWW-Authenticate':'Bearer'})
    user = db.get(Employee, employee_id)
    if not user or user.is_deleted or user.status != 'active' or user.email != email:
        raise HTTPException(401, 'Employee is not active')
    return {'current_user_id':user.id, 'current_user_email':user.email,
            'current_user_role':user.role, 'current_user_name':user.name,
            'current_user_leave_balance':user.leave_balances or {}}

def require_admin(user: dict = Depends(get_current_employee)) -> dict:
    if user['current_user_role'].lower() not in ('admin','hr'):
        raise HTTPException(403, 'Admin or HR access required')
    return user
