"""One-time local MVP initializer; use Alembic migrations for production."""
from src.database.database_connection import Base, engine
import src.database.models  # ensure employees table registration
from src.hr_management_agent.opd.service import OPDClaim
from src.hr_management_agent.opd.conversation import OPDDraft

if __name__ == '__main__':
    Base.metadata.create_all(bind=engine, tables=[OPDClaim.__table__, OPDDraft.__table__], checkfirst=True)
    print('Local OPD claims table ready.')
