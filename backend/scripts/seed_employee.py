"""Create a synthetic test user in the isolated PostgreSQL database."""
import argparse
from getpass import getpass
from src.database.database_connection import SessionLocal
from src.database.models import Employee
from src.hr_management_agent.auth.authenticate import hash_password

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--email',required=True)
    p.add_argument('--name',default='Test Employee')
    p.add_argument('--role',choices=['user','admin','hr'],default='admin')
    args=p.parse_args()
    password=getpass('Test employee password: ')
    if len(password)<10: raise SystemExit('Choose a password with at least 10 characters.')
    with SessionLocal() as db:
        if db.query(Employee).filter_by(email=args.email.lower()).first(): raise SystemExit('Email already exists.')
        row=Employee(email=args.email.lower(),name=args.name,password=hash_password(password),
                     role=args.role,leave_balances={'annual':14,'casual':12},status='active',is_deleted=False)
        db.add(row);db.commit()
        print(f'Created test employee id={row.id} email={row.email} role={row.role}')
