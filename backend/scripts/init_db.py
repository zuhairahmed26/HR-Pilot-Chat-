"""DEV bootstrap for the isolated prototype database ONLY. Alembic should replace this for later changes."""
from src.database.database_connection import Base,engine
import src.database.models  # register metadata

if __name__=='__main__':
    Base.metadata.create_all(bind=engine)
    print('Isolated prototype tables initialized.')
