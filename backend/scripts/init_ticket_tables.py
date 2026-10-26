"""Create local ticket tables only; retains existing database data."""
from src.database.database_connection import Base, engine
import src.database.models  # register employees table
from src.hr_management_agent.tickets.service import TicketDraft, SupportTicket

if __name__ == '__main__':
    Base.metadata.create_all(bind=engine, tables=[TicketDraft.__table__, SupportTicket.__table__], checkfirst=True)
    print('Local ticket draft and support-ticket tables ready.')
