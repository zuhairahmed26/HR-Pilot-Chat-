import json
import redis
from src.core.config import get_settings

settings = get_settings()
cache = redis.Redis(host=settings.REDIS_HOST,port=settings.REDIS_PORT,db=1,decode_responses=True,
                    socket_connect_timeout=3,socket_timeout=3)

def set_session(session_id: str, owner_id: int, messages: list):
    cache.setex(f'chat:{session_id}',settings.CHAT_SESSION_TTL_SECONDS,
                json.dumps({'employee_id': owner_id,'messages':messages}))

def delete_session(session_id: str):
    cache.delete(f'chat:{session_id}')
