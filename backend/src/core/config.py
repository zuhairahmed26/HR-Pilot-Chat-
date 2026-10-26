from functools import lru_cache
from urllib.parse import quote
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', str_strip_whitespace=True)
    APP_ENV: str = 'dev'
    BACKEND_URL: str = 'http://127.0.0.1:8001'
    CORS_ORIGINS: str = 'http://localhost:5173,http://127.0.0.1:5173'
    DB_HOST: str = '127.0.0.1'
    DB_PORT: int = 55432
    DB_NAME: str = 'hr_pilot_cohere'
    DB_USER: str = 'hr_cohere'
    DB_PASSWORD: str
    DATABASE_URL: str | None = None
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = 'HS256'
    REDIS_HOST: str = '127.0.0.1'
    REDIS_PORT: int = 56379
    CHAT_SESSION_TTL_SECONDS: int = Field(default=7200, ge=60)
    VECTOR_DB_HOST: str = '127.0.0.1'
    VECTOR_DB_PORT: int = 16333
    VECTOR_COLLECTION_NAME: str = 'policy_collection'
    VECTOR_DIMENSION: int = 2048
    COHERE_API_KEY: str
    COHERE_CHAT_MODEL: str = 'command-a-plus-05-2026'
    COHERE_EMBED_MODEL: str = 'embed-v5.0-pro'
    MAX_POLICY_UPLOAD_MB: int = 15

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL: return self.DATABASE_URL
        return (f'postgresql+psycopg2://{quote(self.DB_USER, safe="")}:'
                f'{quote(self.DB_PASSWORD, safe="")}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}')

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(',') if x.strip()]

    @model_validator(mode='after')
    def check_secrets(self):
        if self.SECRET_KEY.startswith('REPLACE_') or self.COHERE_API_KEY == 'REPLACE_ME':
            raise ValueError('Configure SECRET_KEY and COHERE_API_KEY in .env')
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
