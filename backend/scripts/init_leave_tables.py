"""Create only the two new prototype leave tables; existing HR tables are untouched."""
from src.database.database_connection import Base, engine
import src.database.models  # register employees table for foreign-key resolution
from src.hr_management_agent.leave.service import LeaveDraft, LeaveRequest

if __name__ == '__main__':
    Base.metadata.create_all(bind=engine, tables=[LeaveDraft.__table__, LeaveRequest.__table__], checkfirst=True)
    print('Local leave draft and request tables ready.')
