from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from src.core.config import get_settings
from src.database.database_connection import engine
from src.hr_management_agent.auth.api import router as auth_router
from src.hr_management_agent.auth.authenticate import require_admin
from src.hr_management_agent.chat.api import router as chat_router
from src.hr_management_agent.policy_vector_store.api import router as policy_router

settings=get_settings()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run `python -m scripts.init_db` once first; do not alter schema automatically.
    yield

def create_app():
    app=FastAPI(title='HR Pilot — Cohere Prototype',version='0.1.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,
                       allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
    @app.get('/health')
    def health(): return {'status':'ok','service':'hr-pilot-cohere'}
    @app.get('/health/dependencies')
    def dependencies(user: dict = Depends(require_admin)):
        from src.hr_management_agent.chat.redis_client import cache
        from src.hr_management_agent.policy_vector_store.utils import qdrant
        results={}
        try:
            with engine.connect() as con: con.execute(text('SELECT 1'))
            results['postgres']='ok'
        except Exception: results['postgres']='unavailable'
        try: results['redis']='ok' if cache.ping() else 'unavailable'
        except Exception: results['redis']='unavailable'
        try: qdrant.get_collections();results['qdrant']='ok'
        except Exception: results['qdrant']='unavailable'
        return results
    app.include_router(auth_router);app.include_router(chat_router);app.include_router(policy_router)
    return app
app=create_app()
